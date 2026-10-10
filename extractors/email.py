import re


EMAIL_RE = re.compile(
    r"(?i)(?<![\w.%+-])"
    r"[a-z0-9.!#$%&'*+=?^_`{|}~-]+"
    r"@"
    r"[a-z0-9-]+"
    r"(?:\.[a-z0-9-]+)+"
    r"\b"
)

_ASSET_TLDS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "avif",
    "css", "js", "mjs", "map", "json", "xml", "html", "htm", "php",
    "woff", "woff2", "ttf", "otf", "eot", "mp4", "webm", "mp3", "pdf",
}


def _looks_like_email(candidate: str) -> bool:
    domain = candidate.rsplit("@", 1)[1].lower()
    tld = domain.rsplit(".", 1)[1]
    if not tld.isalpha() or len(tld) < 2 or tld in _ASSET_TLDS:
        return False
    if re.fullmatch(r"\d+x", domain.split(".")[0]):
        return False
    return True


def extract_emails(text: str) -> list[str]:
    return sorted({m for m in EMAIL_RE.findall(text) if _looks_like_email(m)})
