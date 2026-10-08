import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractors.email import extract_emails
from extractors.email_classification import classify_email
from extractors.link_filter import is_interesting_link
from extractors.links import extract_links
from extractors.mail_provider import identify_provider
from extractors.metadata import extract_metadata
from extractors.public_identity import (
    extract_name_candidates, extract_structured_names, extract_usernames,
    extract_visible_text, extract_text_blocks,
)

HTML = """<html><head><title>Hi</title>
<meta name="description" content="desc"><meta property="og:title" content="OT">
<script type="application/ld+json">{"@type": "Person", "name": "John Smith"}</script>
</head><body><p>Author: John Smith, reach me @johnny on https://x.com/johnny</p>
<a href="/about">a</a><a href="mailto:a@b.co">m</a><a href="javascript:void(0)">j</a>
<script>var hidden = 1</script></body></html>"""


class Email(unittest.TestCase):
    def test_extract_dedupe_sorted(self):
        self.assertEqual(extract_emails("B@x.org a@x.org a@x.org"), ["B@x.org", "a@x.org"])

    def test_not_emails(self):
        self.assertEqual(extract_emails("no mail here, twitter @handle, a@b"), [])

    def test_classification(self):
        self.assertEqual(classify_email("a@example.com"), "test")
        self.assertEqual(classify_email("INFO@site.ru"), "technical")
        self.assertEqual(classify_email("john@gmail.com"), "personal_candidate")
        self.assertEqual(classify_email("nope"), "invalid")

    def test_provider(self):
        self.assertEqual(identify_provider("a@gmail.com"), "Google")
        self.assertEqual(identify_provider("a@yandex.ru"), "Yandex")
        self.assertEqual(identify_provider("a@mycompany.io"), "custom")
        self.assertEqual(identify_provider("nope"), "unknown")


class Links(unittest.TestCase):
    def test_extract_links_absolute_only_http(self):
        self.assertEqual(extract_links(HTML, "https://e.com/x/"), ["https://e.com/about"])

    def test_interesting(self):
        self.assertTrue(is_interesting_link("https://e.com/about"))
        self.assertTrue(is_interesting_link("https://e.com/contacts/team"))
        self.assertFalse(is_interesting_link("https://e.com/blog"))
        self.assertFalse(is_interesting_link("https://e.com/about/file.zip"))
        self.assertFalse(is_interesting_link("mailto:a@b.co"))


class Metadata(unittest.TestCase):
    def test_metadata(self):
        m = extract_metadata(HTML)
        self.assertEqual((m["title"], m["description"], m["og_title"]), ("Hi", "desc", "OT"))
        self.assertEqual(m["og_url"], "")


class Identity(unittest.TestCase):
    def test_visible_text_skips_scripts(self):
        text = extract_visible_text(HTML)
        self.assertIn("reach me", text)
        self.assertNotIn("hidden", text)

    def test_text_blocks_and_usernames(self):
        self.assertTrue(any("@johnny" in b for b in extract_text_blocks(HTML)))
        self.assertEqual(extract_usernames(extract_visible_text(HTML)), ["johnny"])

    def test_name_candidates_need_capital_letters(self):
        names = extract_name_candidates("Author: John Smith and written by Anna Lee, name: bob lowercase")
        self.assertEqual(names, ["John Smith", "Anna Lee"])

    def test_structured_names(self):
        self.assertEqual(extract_structured_names(HTML), ["John Smith"])


if __name__ == "__main__":
    unittest.main()
