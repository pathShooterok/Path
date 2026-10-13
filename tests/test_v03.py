import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import cache, engine
from core.blocks import is_block_page
from core.config import load_config
from core.correlate import correlate_profiles
from core.models import Finding, new_report
from extractors.social import parse_social_url
from output.html_report import render_html
from sources import profiles


def fake(body):
    return {"ok": True, "status": 200, "final_url": "x", "headers": {},
            "data": body, "truncated": False, "error": None}


def missing(url):
    return {"ok": False, "status": 404, "final_url": url, "headers": {},
            "data": b"", "truncated": False, "error": "HTTP 404"}


class Cache(unittest.TestCase):
    def test_store_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_config(overrides={"cache": {"enabled": True, "dir": tmp, "ttl": 60}})
            result = {**fake(b"hello"), "headers": {"Content-Type": "text/html"}}
            self.assertIsNone(cache.load("https://a.example/", None))
            cache.store("https://a.example/", None, result)
            hit = cache.load("https://a.example/", None)
            self.assertEqual(hit["data"], b"hello")
            self.assertTrue(hit["cached"])
            self.assertEqual(hit["headers"].get("Content-Type"), "text/html")
            self.assertIsNone(cache.load("https://a.example/", {"Accept": "x"}))

    def test_skips_blocks_errors_and_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_config(overrides={"cache": {"enabled": True, "dir": tmp, "ttl": 60}})
            cache.store("https://b.example/", None, fake(b"<html>Please solve the CAPTCHA</html>"))
            cache.store("https://c.example/", None, missing("https://c.example/"))
            self.assertIsNone(cache.load("https://b.example/", None))
            self.assertIsNone(cache.load("https://c.example/", None))
            cache.store("https://d.example/", None, fake(b"ok"))
            with mock.patch("core.cache.time.time", return_value=10 ** 11):
                self.assertIsNone(cache.load("https://d.example/", None))

    def test_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_config(overrides={"cache": {"enabled": False, "dir": tmp}})
            cache.store("https://e.example/", None, fake(b"ok"))
            self.assertIsNone(cache.load("https://e.example/", None))
            self.assertEqual(list(Path(tmp).iterdir()), [])


class Blocks(unittest.TestCase):
    def test_detect(self):
        self.assertTrue(is_block_page("Our systems have detected unusual traffic"))
        self.assertTrue(is_block_page("<div>Verify you are a human</div>"))
        self.assertFalse(is_block_page("<html>just a normal page</html>"))


class ApiProbes(unittest.TestCase):
    def setUp(self):
        load_config(overrides={"cache": {"enabled": False}, "sources": {"delay_between": 0}})

    def run_probe(self, name, user, payload):
        def fake_fetch(url, headers=None, timeout=None):
            if "ycombinator" in url or "firebaseio" in url or "docker" in url \
                    or "bsky" in url or "keybase" in url:
                return fake(json.dumps(payload).encode())
            return missing(url)

        with mock.patch("sources.profiles.fetch", side_effect=fake_fetch):
            return profiles.probe_profiles(user, platforms=[name])

    def test_hackernews(self):
        r = self.run_probe("HackerNews", "pgx", {"id": "pgx", "about": "Writer, pg@example.org"})
        self.assertEqual(r[0]["fields"]["bio"], "Writer, pg@example.org")
        self.assertEqual(self.run_probe("HackerNews", "pgx", None), [])

    def test_dockerhub(self):
        r = self.run_probe("DockerHub", "bobadev", {"id": "1", "full_name": "Boba B",
                                                    "location": "Berlin", "company": "Acme",
                                                    "gravatar_email": "boba@acme.dev"})
        f = r[0]["fields"]
        self.assertEqual((f["name"], f["location"], f["company"], f["email"]),
                         ("Boba B", "Berlin", "Acme", "boba@acme.dev"))

    def test_bluesky(self):
        r = self.run_probe("Bluesky", "boba", {"did": "did:plc:1", "displayName": "Boba",
                                               "description": "hello"})
        self.assertEqual(r[0]["fields"]["name"], "Boba")
        self.assertEqual(self.run_probe("Bluesky", "boba", {"error": "InvalidRequest"}), [])

    def test_keybase_proofs(self):
        payload = {"status": {"code": 0}, "them": [{
            "basics": {"username": "boba"},
            "profile": {"full_name": "Boba B", "location": "Oslo", "bio": "crypto"},
            "proofs_summary": {"all": [
                {"service_url": "https://github.com/bobagh"},
                {"service_url": "https://twitter.com/bobatw"}]}}]}
        r = self.run_probe("Keybase", "boba", payload)
        self.assertEqual(r[0]["fields"]["name"], "Boba B")
        self.assertIn("https://github.com/bobagh", r[0]["proofs"])


class Engine(unittest.TestCase):
    def setUp(self):
        load_config(overrides={"cache": {"enabled": False}})

    def test_profile_fields_become_findings(self):
        report = new_report("boba")
        profile = {"platform": "Codeberg", "username": "boba", "url": "https://codeberg.org/boba"}
        fields = {"name": "Boba B", "bio": "see https://x.com/bobatw or mail me at me@boba.dev",
                  "location": "Oslo", "website": "boba.dev", "email": ""}
        engine._add_profile_fields(report, profile, fields, "profile_probe", "medium",
                                   extra_links=["https://github.com/bobagh"])
        got = {(f.kind, f.value) for f in report.findings}
        self.assertIn(("name", "Boba B"), got)
        self.assertIn(("text", "Oslo"), got)
        self.assertIn(("link", "https://boba.dev"), got)
        self.assertIn(("email", "me@boba.dev"), got)
        self.assertIn(("linked_social", "X: https://x.com/bobatw"), got)
        self.assertIn(("linked_social", "GitHub: https://github.com/bobagh"), got)


class NewPlatforms(unittest.TestCase):
    def test_parse(self):
        cases = {
            "https://news.ycombinator.com/user?id=pgx": ("HackerNews", "pgx"),
            "https://hub.docker.com/u/bobadev": ("DockerHub", "bobadev"),
            "https://lichess.org/@/Boba": ("Lichess", "Boba"),
            "https://www.chess.com/member/boba": ("Chess.com", "boba"),
            "https://codeberg.org/boba": ("Codeberg", "boba"),
            "https://pypi.org/user/boba/": ("PyPI", "boba"),
            "https://www.npmjs.com/~boba": ("npm", "boba"),
            "https://replit.com/@boba": ("Replit", "boba"),
            "https://codeforces.com/profile/boba": ("Codeforces", "boba"),
            "https://leetcode.com/u/boba/": ("LeetCode", "boba"),
            "https://linktr.ee/boba": ("Linktree", "boba"),
        }
        for url, (platform, user) in cases.items():
            item = parse_social_url(url)
            self.assertEqual((item["platform"], item["username"]), (platform, user), url)

    def test_rejects_non_profiles(self):
        self.assertIsNone(parse_social_url("https://news.ycombinator.com/item?id=1"))
        self.assertIsNone(parse_social_url("https://news.ycombinator.com/user"))
        self.assertIsNone(parse_social_url("https://codeberg.org/explore"))


class Correlation(unittest.TestCase):
    def build(self, extra):
        report = new_report("boba")
        for platform, url in (("GitHub", "https://github.com/boba"), ("Codeberg", "https://codeberg.org/boba")):
            report.findings.append(Finding(kind="social", value=f"{platform}: {url}", source=url,
                                           evidence="x", confidence="medium"))
        report.findings.extend(extra)
        correlate_profiles(report, "boba")
        return [f for f in report.findings if f.kind == "correlation"]

    def test_shared_website(self):
        site = lambda u: Finding(kind="link", value="https://boba.dev/about", source=u,
                                 evidence="Website from X public profile", confidence="high")
        result = self.build([site("https://github.com/boba"), site("https://codeberg.org/boba")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].confidence, "high")
        self.assertIn("shared website: boba.dev", result[0].evidence)

    def test_shared_email(self):
        mail = lambda u: Finding(kind="email", value="Me@Boba.dev", source=u, evidence="x")
        result = self.build([mail("https://github.com/boba"), mail("https://codeberg.org/boba")])
        self.assertEqual(len(result), 1)
        self.assertIn("shared email", result[0].evidence)

    def test_social_hosts_ignored(self):
        site = lambda u: Finding(kind="link", value="https://github.com/other", source=u,
                                 evidence="Website from X public profile", confidence="high")
        result = self.build([site("https://github.com/boba"), site("https://codeberg.org/boba")])
        self.assertEqual(result, [])


class Html(unittest.TestCase):
    def test_escaping_and_links(self):
        report = new_report("<script>alert(1)</script>")
        report.findings = [
            Finding(kind="link", value="javascript:alert(1)", source="javascript:alert(2)",
                    evidence="<b>bold</b>", confidence="high"),
            Finding(kind="social", value='X: https://x.com/a"onmouseover="x', source="https://x.com/a",
                    evidence="e", confidence="low"),
            Finding(kind="email", value="a@b.dev", source="https://b.dev/", evidence="e",
                    confidence="medium", classification="personal_candidate", provider="b.dev"),
        ]
        page = render_html(report)
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("<b>bold", page)
        self.assertNotIn('href="javascript', page)
        self.assertNotIn('"onmouseover="', page)
        self.assertIn("a@b.dev", page)

    def test_empty(self):
        self.assertIn("No public findings", render_html(new_report("x")))


if __name__ == "__main__":
    unittest.main()
