import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import load_config
from sources.duckduckgo import search_duckduckgo
from sources.bing import search_bing
from core import engine

DDG = b'''
<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Fjohndoe&rut=x">johndoe (John)</a>
<a class="result__snippet" href="#">Mail me: john@gmail.com or t.me/johndoe</a></div>
<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage">Other</a>
<a class="result__snippet" href="#">nothing</a></div>
'''

BING = b'''
<ol><li class="b_algo"><h2><a href="https://twitter.com/john_doe">john_doe on X</a></h2>
<div class="b_caption"><p>Official account</p></div></li></ol>
'''


def fake(body):
    return {"ok": True, "status": 200, "final_url": "x", "headers": {},
            "data": body, "truncated": False, "error": None}


class Sources(unittest.TestCase):
    def setUp(self):
        load_config()

    def test_ddg(self):
        with mock.patch("sources.duckduckgo.fetch", return_value=fake(DDG)):
            r = search_duckduckgo('"johndoe"')
        self.assertEqual(r[0]["url"], "https://github.com/johndoe")
        self.assertIn("john@gmail.com", r[0]["snippet"])
        self.assertEqual(len(r), 2)

    def test_bing(self):
        with mock.patch("sources.bing.fetch", return_value=fake(BING)):
            r = search_bing('"john_doe"')
        self.assertEqual(r[0]["url"], "https://twitter.com/john_doe")
        self.assertEqual(r[0]["snippet"], "Official account")

    def test_trace_end_to_end(self):
        profile_html = ('<html><title>John</title><meta name="description" content="hi">'
                        '<a href="https://t.me/johndoe">tg</a>contact: johndoe.real@proton.me</html>')
        page = {"url": "", "final_url": "https://github.com/johndoe", "status": 200,
                "content_type": "text/html", "text": profile_html, "error": None}
        with mock.patch("sources.duckduckgo.fetch", return_value=fake(DDG)), \
             mock.patch("sources.bing.fetch", return_value=fake(BING)), \
             mock.patch("core.engine.fetch_url", return_value=page), \
             mock.patch("core.engine.probe_profiles", return_value=[]), \
             mock.patch("sources.time.sleep"):
            rep = engine.run_trace("johndoe")
        kinds = {(f.kind, f.value) for f in rep.findings}
        self.assertIn(("social", "GitHub: https://github.com/johndoe"), kinds)
        self.assertIn(("email", "john@gmail.com"), kinds)
        self.assertIn(("email", "johndoe.real@proton.me"), kinds)
        self.assertIn(("linked_social", "Telegram: https://t.me/johndoe"), kinds)
        # john_doe (normalized) fetched too; example.com is not a profile
        self.assertTrue(any(f.kind == "social" and "x.com/john_doe" in f.value for f in rep.findings))

    def test_relevance_filter_drops_noise(self):
        noise = {"title": "Bubble tea - Wikipedia", "url": "https://en.wikipedia.org/wiki/Bubble_tea",
                 "snippet": "boba drink", "source": "bing"}
        hit = {"title": "boba_40404 - profile", "url": "https://example.org/u/boba_40404",
               "snippet": "", "source": "bing"}
        with mock.patch("core.engine.run_search", return_value=[noise, hit]), \
             mock.patch("core.engine.probe_profiles", return_value=[]):
            rep = engine.run_trace("boba_40404")
        urls = [f.source for f in rep.findings if f.kind == "web_result"]
        self.assertEqual(urls, ["https://example.org/u/boba_40404"])

    def test_probe_and_github_api(self):
        html = "<html><title>boba</title>mail: public@boba.dev</html>"
        probe = [{"platform": "GitHub", "username": "boba", "url": "https://github.com/boba", "html": html}]
        api = {"name": "Boba B", "email": "api@boba.dev", "blog": "boba.dev",
               "twitter_username": "bobatw", "bio": "hi", "location": None, "company": None}
        with mock.patch("core.engine.run_search", return_value=[]), \
             mock.patch("core.engine.probe_profiles", return_value=probe), \
             mock.patch("core.engine.github_api", return_value=api):
            rep = engine.run_trace("boba")
        kinds = {(f.kind, f.value) for f in rep.findings}
        self.assertIn(("social", "GitHub: https://github.com/boba"), kinds)
        self.assertIn(("email", "api@boba.dev"), kinds)
        self.assertIn(("email", "public@boba.dev"), kinds)
        self.assertIn(("name", "Boba B"), kinds)
        self.assertIn(("link", "https://boba.dev"), kinds)
        self.assertIn(("linked_social", "X: https://x.com/bobatw"), kinds)


class Extractors(unittest.TestCase):
    def test_email_ignores_asset_names(self):
        from extractors.email import extract_emails
        text = ('<img src="images/badges/install-badge-linux-168-56@2x.png"> '
                'logo@3x.webp icon@2x.svg mail: real.person@example.org, other@mail.ru.')
        self.assertEqual(extract_emails(text), ["other@mail.ru", "real.person@example.org"])

    def test_same_platform_links_dropped_on_profile_page(self):
        rep = engine.new_report("x")
        links = ["https://github.com/contact", "https://github.com/pricing",
                 "https://github.com/x", "https://t.me/x_chan", "https://x.com/someone"]
        engine._add_social_findings(rep, links, "https://github.com/x", "profile_probe", linked=True,
                                    outbound_only=True)
        vals = {f.value for f in rep.findings}
        self.assertEqual(vals, {"Telegram: https://t.me/x_chan", "X: https://x.com/someone"})


class Probes(unittest.TestCase):
    def setUp(self):
        load_config()

    def test_probe_exists_and_validity(self):
        from sources import profiles

        def fake_fetch(url, headers=None, timeout=None):
            if "github.com/boba" in url:
                return {**fake(b"<html>ok</html>"), "final_url": url}
            if "t.me/boba" in url:  # generic Telegram page without profile marker
                return {**fake(b"<html>Contact</html>"), "final_url": url}
            return {"ok": False, "status": 404, "final_url": url, "headers": {},
                    "data": b"", "truncated": False, "error": "HTTP 404"}

        with mock.patch("sources.profiles.fetch", side_effect=fake_fetch), \
             mock.patch("sources.profiles.time.sleep"):
            r = profiles.probe_profiles("boba")
        self.assertEqual([p["platform"] for p in r], ["GitHub"])  # t.me needs marker; "boba" < 5 chars anyway

        with mock.patch("sources.profiles.fetch", side_effect=fake_fetch), \
             mock.patch("sources.profiles.time.sleep"):
            self.assertEqual(profiles.probe_profiles("bad name!"), [])

    def test_variants_and_gitlab_api(self):
        from sources import profiles

        self.assertEqual(profiles.username_variants("boba_40404"),
                         ["boba_40404", "boba-40404", "boba40404"])

        def fake_fetch(url, headers=None, timeout=None):
            if "github.com/boba-40404" in url:
                return {**fake(b"<html>ok</html>"), "final_url": url}
            if "api/v4/users?username=boba_40404" in url:
                return fake(b'[{"username": "boba_40404", "name": "Boba", "web_url": "https://gitlab.com/boba_40404"}]')
            if "api/v4/users" in url:
                return fake(b"[]")
            return {"ok": False, "status": 404, "final_url": url, "headers": {},
                    "data": b"", "truncated": False, "error": "HTTP 404"}

        with mock.patch("sources.profiles.fetch", side_effect=fake_fetch), \
             mock.patch("sources.profiles.time.sleep"):
            r = {p["platform"]: p for p in profiles.probe_profiles("boba_40404")}
        self.assertTrue(r["GitHub"]["variant"])          # underscore invalid on GitHub -> boba-40404
        self.assertEqual(r["GitHub"]["username"], "boba-40404")
        self.assertFalse(r["GitLab"]["variant"])
        self.assertEqual(r["GitLab"]["name"], "Boba")


if __name__ == "__main__":
    unittest.main()
