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
             mock.patch("sources.time.sleep"):
            rep = engine.run_trace("johndoe")
        kinds = {(f.kind, f.value) for f in rep.findings}
        self.assertIn(("social", "GitHub: https://github.com/johndoe"), kinds)
        self.assertIn(("email", "john@gmail.com"), kinds)
        self.assertIn(("email", "johndoe.real@proton.me"), kinds)
        self.assertIn(("linked_social", "Telegram: https://t.me/johndoe"), kinds)
        # john_doe (normalized) fetched too; example.com is not a profile
        self.assertTrue(any(f.kind == "social" and "x.com/john_doe" in f.value for f in rep.findings))


if __name__ == "__main__":
    unittest.main()
