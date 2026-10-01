from urllib.parse import urlparse


INTERESTING_KEYWORDS = {
    "about",
    "bio",
    "contact",
    "contacts",
    "profile",
    "social",
    "links",
    "info",
    "email",
    "help",
    "support",
}


IGNORED_PREFIXES = {
    "javascript:",
    "mailto:",
    "tel:",
}


IGNORED_EXTENSIONS = {
    ".zip",
    ".rar",
    ".7z",
    ".exe",
    ".msi",
    ".iso",
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
}


def is_interesting_link(url: str) -> bool:
    lower_url = url.lower()

    for prefix in IGNORED_PREFIXES:
        if lower_url.startswith(prefix):
            return False

    parsed = urlparse(url)
    path = parsed.path.lower()

    for extension in IGNORED_EXTENSIONS:
        if path.endswith(extension):
            return False

    return any(
        keyword in path
        for keyword in INTERESTING_KEYWORDS
    )