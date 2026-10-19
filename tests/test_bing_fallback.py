import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import load_config
from sources.bing import search_bing

PAGE = b"""
<html><body>
<h2><a href="https://www.bing.com/images/search?q=x">Images</a></h2>
<div class="answer"><h2><a href="https://phew.example/profile">Phew - profile</a></h2>
<p>Some <b>snippet</b> text</p></div>
<h2><a href="https://example.dev/page">Another result</a></h2><div><p>Second snippet</p></div>
</body></html>
"""

STANDARD = b"""
<ol><li class="b_algo"><h2><a href="https://one.example/">One</a></h2><p>Snippet one</p></li></ol>
"""


def fake(body):
    return {"ok": True, "status": 200, "final_url": "x", "headers": {},
            "data": body, "truncated": False, "error": None}


class BingFallback(unittest.TestCase):
    def setUp(self):
        load_config(overrides={"cache": {"enabled": False}})

    def test_fallback_when_blocks_missing(self):
        with mock.patch("sources.bing.fetch", return_value=fake(PAGE)):
            results = search_bing('"Phew"')
        self.assertEqual([r["url"] for r in results],
                         ["https://phew.example/profile", "https://example.dev/page"])
        self.assertEqual(results[0]["snippet"], "Some snippet text")

    def test_standard_blocks_take_priority(self):
        with mock.patch("sources.bing.fetch", return_value=fake(STANDARD + PAGE)):
            results = search_bing('"x"')
        self.assertEqual([r["url"] for r in results], ["https://one.example/"])

    def test_nothing_found(self):
        with mock.patch("sources.bing.fetch", return_value=fake(b"<html>empty</html>")):
            self.assertEqual(search_bing('"x"'), [])

    def test_captcha_is_not_parsed(self):
        with mock.patch("sources.bing.fetch", return_value=fake(b"<html>Please solve the CAPTCHA " + PAGE + b"</html>")):
            self.assertEqual(search_bing('"x"'), [])



NO_RESULTS = b'<ol id="b_results"><li class="b_no"><h1>There are no results for <strong>"Phew"</strong></h1></li></ol>'


class BingNoResults(unittest.TestCase):
    def setUp(self):
        load_config(overrides={"cache": {"enabled": False}})

    def test_retries_without_quotes(self):
        pages = [fake(NO_RESULTS), fake(STANDARD)]
        with mock.patch("sources.bing.fetch", side_effect=pages) as call:
            results = search_bing('"Phew"')
        self.assertEqual([r["url"] for r in results], ["https://one.example/"])
        self.assertEqual(call.call_count, 2)
        self.assertNotIn("%22", call.call_args_list[1][0][0])

    def test_gives_up_after_retry(self):
        with mock.patch("sources.bing.fetch", return_value=fake(NO_RESULTS)) as call:
            self.assertEqual(search_bing('"Phew"'), [])
        self.assertEqual(call.call_count, 2)

    def test_unquoted_query_is_not_retried(self):
        with mock.patch("sources.bing.fetch", return_value=fake(NO_RESULTS)) as call:
            self.assertEqual(search_bing("Phew"), [])
        self.assertEqual(call.call_count, 1)


if __name__ == "__main__":
    unittest.main()
