import re
from urllib.parse import urlparse, unquote

_U = r"[A-Za-z0-9_.\-]{1,64}"

PLATFORMS = [
    {"name": "GitHub", "hosts": ["github.com"],
     "paths": [rf"^/(?P<user>{_U})/?$"],
     "reserved": {"features", "pricing", "about", "login", "join", "explore", "topics",
                  "marketplace", "orgs", "settings", "sponsors", "search", "notifications",
                  "pulls", "issues", "enterprise", "collections", "trending", "security",
                  "apps", "readme", "site", "customer-stories", "events"},
     "canonical": "https://github.com/{user}"},
    {"name": "GitLab", "hosts": ["gitlab.com"],
     "paths": [rf"^/(?P<user>{_U})/?$"],
     "reserved": {"users", "explore", "help", "dashboard", "groups", "projects", "admin"},
     "canonical": "https://gitlab.com/{user}"},
    {"name": "YouTube", "hosts": ["youtube.com", "m.youtube.com"],
     "paths": [r"^/@(?P<user>[^/?#]{2,64})", r"^/(?:c|user)/(?P<user>[^/?#]+)",
               r"^/channel/(?P<user>UC[\w-]{20,24})"],
     "reserved": set(),
     "canonical": "https://www.youtube.com/@{user}"},
    {"name": "Twitch", "hosts": ["twitch.tv", "m.twitch.tv"],
     "paths": [r"^/(?P<user>[A-Za-z0-9_]{3,25})/?$"],
     "reserved": {"directory", "videos", "downloads", "jobs", "turbo", "store", "settings",
                  "p", "login", "signup", "search", "friends", "subscriptions"},
     "canonical": "https://www.twitch.tv/{user}"},
    {"name": "TikTok", "hosts": ["tiktok.com"],
     "paths": [r"^/@(?P<user>[A-Za-z0-9_.]{2,24})"],
     "reserved": set(),
     "canonical": "https://www.tiktok.com/@{user}"},
    {"name": "VK", "hosts": ["vk.com", "vk.ru", "m.vk.com", "m.vk.ru"],
     "paths": [rf"^/(?P<user>(?:id\d+|club\d+|public\d+|[A-Za-z][A-Za-z0-9_.]{{3,31}}))/?$"],
     "reserved": {"feed", "login", "away", "share", "video", "audio", "photo", "wall",
                  "im", "friends", "groups", "search", "music", "market", "apps",
                  "settings", "edit", "restore", "join", "dev", "about", "support",
                  "terms", "blog", "doc", "al_feed", "clips", "stickers"},
     "canonical": "https://vk.com/{user}"},
    {"name": "Instagram", "hosts": ["instagram.com"],
     "paths": [r"^/(?P<user>[A-Za-z0-9_.]{1,30})/?$"],
     "reserved": {"p", "reel", "reels", "explore", "accounts", "stories", "direct", "about",
                  "legal", "developer", "directory", "tv", "web", "challenge", "emails"},
     "canonical": "https://www.instagram.com/{user}/"},
    {"name": "X", "hosts": ["x.com", "twitter.com", "mobile.twitter.com"],
     "paths": [r"^/(?P<user>[A-Za-z0-9_]{1,15})(?:/(?:with_replies|media|likes|status/\d+))?/?$"],
     "reserved": {"home", "explore", "search", "i", "intent", "share", "login", "signup",
                  "settings", "messages", "notifications", "compose", "hashtag", "tos",
                  "privacy", "about", "download", "account", "jobs", "who_to_follow"},
     "canonical": "https://x.com/{user}"},
    {"name": "Reddit", "hosts": ["reddit.com", "old.reddit.com", "new.reddit.com"],
     "paths": [r"^/(?:u|user)/(?P<user>[A-Za-z0-9_\-]{3,20})"],
     "reserved": set(),
     "canonical": "https://www.reddit.com/user/{user}"},
    {"name": "Telegram", "hosts": ["t.me", "telegram.me", "telegram.dog"],
     "paths": [r"^/(?:s/)?(?P<user>[A-Za-z][A-Za-z0-9_]{4,31})/?$"],
     "reserved": {"joinchat", "addstickers", "share", "iv", "proxy", "socks", "login",
                  "addemoji", "setlanguage", "bg", "c", "s"},
     "canonical": "https://t.me/{user}"},
    {"name": "Facebook", "hosts": ["facebook.com", "m.facebook.com", "fb.com"],
     "paths": [r"^/profile\.php$", rf"^/(?P<user>{_U})/?$"],
     "reserved": {"sharer", "sharer.php", "share", "dialog", "login", "login.php", "groups",
                  "pages", "events", "watch", "marketplace", "photo", "photo.php", "help",
                  "policies", "privacy", "tr", "plugins", "gaming", "reel", "stories", "public"},
     "canonical": "https://www.facebook.com/{user}"},
    {"name": "LinkedIn", "hosts": ["linkedin.com"],
     "paths": [r"^/in/(?P<user>[^/?#]{3,100})", r"^/company/(?P<user>[^/?#]+)"],
     "reserved": set(),
     "canonical": "https://www.linkedin.com/in/{user}"},
    {"name": "Pinterest", "hosts": ["pinterest.com", "ru.pinterest.com"],
     "paths": [r"^/(?P<user>[A-Za-z0-9_]{3,30})/?$"],
     "reserved": {"pin", "search", "ideas", "login", "business", "today", "about"},
     "canonical": "https://www.pinterest.com/{user}/"},
    {"name": "Medium", "hosts": ["medium.com"],
     "paths": [r"^/@(?P<user>[A-Za-z0-9_.]{2,40})"],
     "reserved": set(),
     "canonical": "https://medium.com/@{user}"},
    {"name": "Steam", "hosts": ["steamcommunity.com"],
     "paths": [r"^/id/(?P<user>[A-Za-z0-9_\-]{2,32})", r"^/profiles/(?P<user>\d{17})"],
     "reserved": set(),
     "canonical": "https://steamcommunity.com/id/{user}"},
    {"name": "Bluesky", "hosts": ["bsky.app"],
     "paths": [r"^/profile/(?P<user>[A-Za-z0-9.\-]{3,253})"],
     "reserved": set(),
     "canonical": "https://bsky.app/profile/{user}"},
    {"name": "Habr", "hosts": ["habr.com"],
     "paths": [r"^/(?:ru|en)/users/(?P<user>[A-Za-z0-9_\-]{2,32})", r"^/users/(?P<user>[A-Za-z0-9_\-]{2,32})"],
     "reserved": set(),
     "canonical": "https://habr.com/ru/users/{user}/"},
    {"name": "Pikabu", "hosts": ["pikabu.ru"],
     "paths": [r"^/@(?P<user>[A-Za-z0-9_.\-]{2,40})"],
     "reserved": set(),
     "canonical": "https://pikabu.ru/@{user}"},
    {"name": "DEV", "hosts": ["dev.to"],
     "paths": [rf"^/(?P<user>{_U})/?$"],
     "reserved": {"t", "tags", "about", "contact", "search", "enter", "new", "listings",
                  "readinglist", "settings", "videos", "podcasts", "faq", "privacy", "terms"},
     "canonical": "https://dev.to/{user}"},
    {"name": "Keybase", "hosts": ["keybase.io"],
     "paths": [r"^/(?P<user>[A-Za-z0-9_]{2,16})/?$"],
     "reserved": {"download", "blog", "docs", "what-is-keybase", "jobs"},
     "canonical": "https://keybase.io/{user}"},
    {"name": "Behance", "hosts": ["behance.net"],
     "paths": [r"^/(?P<user>[A-Za-z0-9_\-]{2,40})/?$"],
     "reserved": {"search", "galleries", "joblist", "live", "assets", "about", "gallery"},
     "canonical": "https://www.behance.net/{user}"},
]

SUBDOMAIN_PLATFORMS = {
    "livejournal.com": ("LiveJournal", "https://{user}.livejournal.com"),
    "tumblr.com": ("Tumblr", "https://{user}.tumblr.com"),
    "medium.com": ("Medium", "https://medium.com/@{user}"),
    "itch.io": ("itch.io", "https://{user}.itch.io"),
    "bandcamp.com": ("Bandcamp", "https://{user}.bandcamp.com"),
}
_SUBDOMAIN_IGNORE = {"www", "m", "api", "help", "support", "blog", "static", "cdn", "about"}

_HOST_INDEX: dict[str, dict] = {}
for _p in PLATFORMS:
    _p["_paths"] = [re.compile(x) for x in _p["paths"]]
    for _h in _p["hosts"]:
        _HOST_INDEX[_h] = _p

_URL_IN_TEXT = re.compile(
    r"(?i)(?:https?://)?(?:www\.)?"
    r"(?:" + "|".join(re.escape(h) for h in sorted(_HOST_INDEX, key=len, reverse=True)) + r")"
    r"/[^\s\"'<>)\]]+"
)

_MATCH_RANK = {"none": 0, "partial": 1, "normalized": 2, "exact": 3}


def _clean_host(netloc: str) -> str:
    host = netloc.lower().split("@")[-1].split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host


def parse_social_url(url: str) -> dict | None:
    try:
        parsed = urlparse(url if "://" in url else "https://" + url)
    except ValueError:
        return None

    host = _clean_host(parsed.netloc)
    path = unquote(parsed.path or "/")

    platform = _HOST_INDEX.get(host)
    if platform:
        for regex in platform["_paths"]:
            m = regex.match(path)
            if not m:
                continue
            if "user" not in regex.groupindex:
                from urllib.parse import parse_qs
                uid = parse_qs(parsed.query).get("id", [None])[0]
                if not uid or not uid.isdigit():
                    continue
                return {"platform": platform["name"], "username": f"id{uid}",
                        "url": f"https://www.facebook.com/profile.php?id={uid}",
                        "kind": "profile"}
            user = m.group("user")
            if user.lower() in platform["reserved"] or user.startswith("."):
                return None
            return {"platform": platform["name"], "username": user,
                    "url": platform["canonical"].format(user=user), "kind": "profile"}
        return None

    for base, (name, template) in SUBDOMAIN_PLATFORMS.items():
        if host.endswith("." + base):
            sub = host[: -(len(base) + 1)]
            if "." in sub or sub in _SUBDOMAIN_IGNORE:
                return None
            return {"platform": name, "username": sub,
                    "url": template.format(user=sub), "kind": "profile"}
    return None


def extract_social_profiles(links: list[str]) -> list[dict]:
    results, seen = [], set()
    for link in links:
        item = parse_social_url(link)
        if not item:
            continue
        key = (item["platform"], item["username"].lower())
        if key in seen:
            continue
        seen.add(key)
        item["found_as"] = link
        results.append(item)
    return results


def find_social_in_text(text: str) -> list[dict]:
    return extract_social_profiles(
        [m.rstrip(".,;:!?") for m in _URL_IN_TEXT.findall(text or "")]
    )


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def translit(value: str) -> str:
    return "".join(_TRANSLIT.get(ch, ch) for ch in value.lower())


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", translit(value.lstrip("@")))


def match_level(username: str, target: str) -> str:
    u, t = username.lower().lstrip("@"), target.lower().lstrip("@")
    if not u or not t:
        return "none"
    if u == t:
        return "exact"
    un, tn = _norm(u), _norm(t)
    if un and un == tn:
        return "normalized"
    if tn and len(tn) >= 4 and (tn in un or un in tn):
        return "partial"
    return "none"


def match_at_least(level: str, minimum: str) -> bool:
    return _MATCH_RANK.get(level, 0) >= _MATCH_RANK.get(minimum, 2) and level != "none"


def confidence_for(level: str) -> str:
    return {"exact": "high", "normalized": "medium", "partial": "low"}.get(level, "low")
