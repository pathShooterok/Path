import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractors.social import (
    parse_social_url, extract_social_profiles, find_social_in_text, match_level,
)


class SocialParse(unittest.TestCase):
    def check(self, url, platform, user):
        r = parse_social_url(url)
        self.assertIsNotNone(r, url)
        self.assertEqual((r["platform"], r["username"]), (platform, user), url)

    def test_profiles(self):
        self.check("https://github.com/torvalds", "GitHub", "torvalds")
        self.check("https://www.github.com/torvalds/", "GitHub", "torvalds")
        self.check("https://twitter.com/jack", "X", "jack")
        self.check("https://x.com/jack/status/123", "X", "jack")
        self.check("https://t.me/durov", "Telegram", "durov")
        self.check("https://vk.com/id1", "VK", "id1")
        self.check("https://vk.ru/durov", "VK", "durov")
        self.check("https://www.youtube.com/@MrBeast", "YouTube", "MrBeast")
        self.check("https://www.tiktok.com/@scout2015/video/1", "TikTok", "scout2015")
        self.check("https://www.reddit.com/user/spez/comments/x", "Reddit", "spez")
        self.check("https://steamcommunity.com/id/gabelogannewell", "Steam", "gabelogannewell")
        self.check("https://habr.com/ru/users/foo/posts/", "Habr", "foo")
        self.check("https://foo.livejournal.com/123.html", "LiveJournal", "foo")
        self.check("https://www.linkedin.com/in/john-doe-123/", "LinkedIn", "john-doe-123")

    def test_non_profiles(self):
        for url in [
            "https://github.com/features", "https://github.com/login",
            "https://github.com/torvalds/linux",
            "https://t.me/joinchat", "https://t.me/s",
            "https://twitter.com/intent/tweet", "https://www.instagram.com/p/abc/",
            "https://vk.com/feed", "https://example.com/user",
            "https://www.facebook.com/sharer/sharer.php",
        ]:
            self.assertIsNone(parse_social_url(url), url)

    def test_canonical_and_dedup(self):
        r = extract_social_profiles([
            "https://twitter.com/Jack", "https://x.com/jack", "https://mobile.twitter.com/jack",
        ])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["url"], "https://x.com/Jack")

    def test_facebook_profile_php(self):
        r = parse_social_url("https://www.facebook.com/profile.php?id=100001")
        self.assertEqual(r["username"], "id100001")

    def test_text(self):
        r = find_social_in_text("my tg: t.me/foobar, gh https://github.com/baz.")
        self.assertEqual({(p["platform"], p["username"]) for p in r},
                         {("Telegram", "foobar"), ("GitHub", "baz")})

    def test_match(self):
        self.assertEqual(match_level("JohnDoe", "johndoe"), "exact")
        self.assertEqual(match_level("john_doe", "johndoe"), "normalized")
        self.assertEqual(match_level("johndoe99", "johndoe"), "partial")
        self.assertEqual(match_level("alice", "johndoe"), "none")
        self.assertEqual(match_level("ab", "abc"), "none")


if __name__ == "__main__":
    unittest.main()
