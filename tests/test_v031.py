import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import engine
from core.cleanup import clean_report
from core.config import load_config
from core.models import Finding, new_report
from extractors.social import parse_social_url
from sources import discord as discord_source
from sources import profiles


def fake(body):
    return {"ok": True, "status": 200, "final_url": "x", "headers": {},
            "data": body, "truncated": False, "error": None}


def finding(kind, value, source="https://a.example/", confidence="medium", **kw):
    return Finding(kind=kind, value=value, source=source, evidence="e", confidence=confidence, **kw)


class Cleanup(unittest.TestCase):
    def setUp(self):
        load_config(overrides={"cache": {"enabled": False}})

    def report(self, *items):
        r = new_report("t")
        r.findings = list(items)
        return r

    def test_merges_duplicates_and_keeps_best(self):
        r = self.report(
            finding("web_result", "Same", confidence="low"),
            finding("web_result", "Same", confidence="high"),
            finding("link", "https://www.site.dev/page/"),
            finding("link", "https://site.dev/page"),
        )
        stats = clean_report(r)
        self.assertEqual(len(r.findings), 2)
        self.assertEqual(stats["duplicates"], 2)
        self.assertEqual(r.findings[0].confidence, "high")
        self.assertIn("seen 2 times", r.findings[0].evidence)

    def test_social_merge_across_kinds(self):
        r = self.report(
            finding("linked_social", "GitHub: https://github.com/Bob", confidence="medium"),
            finding("social", "GitHub: https://github.com/bob", confidence="medium"),
            finding("social", "X: https://x.com/bob", confidence="low"),
        )
        clean_report(r)
        self.assertEqual([f.value for f in r.findings],
                         ["GitHub: https://github.com/bob", "X: https://x.com/bob"])
        self.assertEqual(r.findings[0].kind, "social")

    def test_placeholder_emails_and_junk_titles(self):
        r = self.report(
            finding("email", "example@example.com"),
            finding("email", "real@boba.dev"),
            finding("email", "a@b.dev", classification="test"),
            finding("title", "Just a moment..."),
            finding("title", "Boba's blog"),
            finding("linked_title", "  "),
        )
        stats = clean_report(r)
        self.assertEqual([f.value for f in r.findings], ["real@boba.dev", "Boba's blog"])
        self.assertEqual(stats["placeholder_emails"], 2)
        self.assertEqual(stats["junk"], 2)

    def test_truncates_long_values_and_keeps_correlation(self):
        r = self.report(finding("text", "x" * 1000),
                        finding("correlation", "GitHub, X"),
                        finding("correlation", "GitHub, X"))
        clean_report(r)
        self.assertLessEqual(len(r.findings[0].value), 300)
        self.assertEqual(len([f for f in r.findings if f.kind == "correlation"]), 2)

    def test_disabled(self):
        load_config(overrides={"cleanup": {"enabled": False}})
        r = self.report(finding("email", "example@example.com"), finding("email", "example@example.com"))
        clean_report(r)
        self.assertEqual(len(r.findings), 2)


class Platforms(unittest.TestCase):
    def test_discord(self):
        a = parse_social_url("https://discord.gg/AbC-123")
        self.assertEqual((a["platform"], a["username"], a["kind"], a["url"]),
                         ("Discord", "AbC-123", "invite", "https://discord.gg/AbC-123"))
        b = parse_social_url("https://discord.com/invite/abc123")
        self.assertEqual(b["url"], "https://discord.gg/abc123")
        c = parse_social_url("https://discord.com/users/123456789012345678")
        self.assertEqual((c["kind"], c["username"]), ("profile", "123456789012345678"))
        self.assertIsNone(parse_social_url("https://discord.com/download"))
        self.assertIsNone(parse_social_url("https://discord.com/somepage"))

    def test_other_platforms(self):
        cases = {
            "https://soundcloud.com/bob": "SoundCloud",
            "https://open.spotify.com/user/bob": "Spotify",
            "https://www.last.fm/user/bob": "Last.fm",
            "https://www.threads.net/@bob": "Threads",
            "https://www.snapchat.com/add/bobby": "Snapchat",
            "https://www.roblox.com/users/12345/profile": "Roblox",
            "https://bitbucket.org/bob/": "Bitbucket",
            "https://hackerone.com/bob": "HackerOne",
        }
        for url, platform in cases.items():
            self.assertEqual(parse_social_url(url)["platform"], platform, url)
        for url in ("https://soundcloud.com/discover", "https://vimeo.com/features",
                    "https://dribbble.com/shots"):
            self.assertIsNone(parse_social_url(url), url)


class Probes(unittest.TestCase):
    def setUp(self):
        load_config(overrides={"cache": {"enabled": False}, "sources": {"delay_between": 0}})

    def probe(self, name, user, payload):
        def fetcher(url, headers=None, timeout=None):
            return fake(json.dumps(payload).encode())

        with mock.patch("sources.profiles.fetch", side_effect=fetcher):
            return profiles.probe_profiles(user, platforms=[name])

    def test_mastodon_strips_html(self):
        r = self.probe("Mastodon", "boba", {"id": "1", "display_name": "Boba",
                                            "note": "<p>Hi &amp; hello<br>mail me</p>"})
        self.assertEqual(r[0]["fields"]["bio"], "Hi & hello\nmail me")

    def test_gravatar_nested(self):
        payload = {"entry": [{"hash": "h", "displayName": "Boba", "aboutMe": "dev",
                              "currentLocation": "Oslo", "urls": [{"value": "https://boba.dev"}]}]}
        r = self.probe("Gravatar", "boba", payload)
        f = r[0]["fields"]
        self.assertEqual((f["name"], f["location"], f["website"]), ("Boba", "Oslo", "https://boba.dev"))
        self.assertEqual(self.probe("Gravatar", "boba", {"entry": []}), [])


class Discord(unittest.TestCase):
    def setUp(self):
        load_config(overrides={"cache": {"enabled": False}})

    def test_invite_info(self):
        body = json.dumps({"code": "abc", "approximate_member_count": 42,
                           "guild": {"name": "Boba Club", "description": "chat"},
                           "inviter": {"username": "boba", "global_name": "Boba"}}).encode()
        with mock.patch("sources.discord.fetch", return_value=fake(body)):
            info = discord_source.invite_info("abc")
        self.assertEqual((info["server"], info["members"], info["inviter"]), ("Boba Club", 42, "boba"))
        with mock.patch("sources.discord.fetch") as call:
            self.assertIsNone(discord_source.invite_info("bad code!"))
            call.assert_not_called()

    def test_engine_adds_findings(self):
        report = new_report("boba")
        report.findings.append(finding("social", "Discord: https://discord.gg/abc",
                                       source="https://discord.gg/abc"))
        info = {"code": "abc", "server": "Boba Club", "description": None, "members": 42,
                "inviter": "boba", "inviter_name": "Boba"}
        with mock.patch("sources.discord.invite_info", return_value=info):
            engine._add_discord_invites(report)
        got = {(f.kind, f.value) for f in report.findings}
        self.assertIn(("text", "Discord server: Boba Club (42 members)"), got)
        self.assertIn(("name", "Boba (@boba)"), got)

    def test_engine_skips_user_links_and_failures(self):
        report = new_report("boba")
        report.findings.append(finding("social", "Discord: https://discord.com/users/123456789012345678"))
        with mock.patch("sources.discord.invite_info") as call:
            engine._add_discord_invites(report)
            call.assert_not_called()
        report.findings.append(finding("social", "Discord: https://discord.gg/abc"))
        with mock.patch("sources.discord.invite_info", return_value=None):
            engine._add_discord_invites(report)
        self.assertEqual(len(report.findings), 2)


if __name__ == "__main__":
    unittest.main()
