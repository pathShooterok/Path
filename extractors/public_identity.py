import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse


USERNAME_RE = re.compile(
    r"(?<![\w@])@([A-Za-z0-9_][A-Za-z0-9._-]{1,31})"
)

NAME_CONTEXT_RE = re.compile(
    r"(?i:"
    r"\bauthor\b\s*[:\-]\s*"
    r"|\bwritten\s+by\b\s*"
    r"|\bby\b\s*[:\-]\s*"
    r"|\bcreated\s+by\b\s*"
    r"|\bposted\s+by\b\s*"
    r"|\bowner\b\s*[:\-]\s*"
    r"|\bname\b\s*[:\-]\s*"
    r"|\bавтор\b\s*[:\-]\s*"
    r"|\bимя\b\s*[:\-]\s*"
    r"|\bсоздано\b\s*[:\-]\s*"
    r"|\bвладелец\b\s*[:\-]\s*"
    r")"
    r"([A-ZА-ЯЁ][a-zа-яё]{2,}"
    r"(?:\s+[A-ZА-ЯЁ][a-zа-яё]{2,}){1,2})"
)

NAME_STOPWORDS = {
    "example domain",
    "example domains",
    "privacy policy",
    "terms service",
    "terms of service",
    "contact us",
    "about us",
    "sign in",
    "sign up",
    "log in",
    "log out",
    "learn more",
    "read more",
    "home page",
    "main page",
}


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.block_parts = []
        self.blocks = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
            return

        if tag in {"h1", "h2", "h3", "p", "li"}:
            self.block_parts = []

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            if self.skip_depth:
                self.skip_depth -= 1
            return

        if tag in {"h1", "h2", "h3", "p", "li"}:
            block = " ".join(self.block_parts)
            block = re.sub(r"\s+", " ", block).strip()

            if block:
                self.blocks.append(block)

            self.block_parts = []

    def handle_data(self, data):
        if self.skip_depth:
            return

        text = re.sub(r"\s+", " ", data).strip()

        if not text:
            return

        self.parts.append(text)
        self.block_parts.append(text)


def extract_visible_text(html: str) -> str:
    parser = VisibleTextParser()

    try:
        parser.feed(html)
    except Exception:
        return ""

    return " ".join(parser.parts)


def extract_text_blocks(html: str, limit: int = 20) -> list[str]:
    parser = VisibleTextParser()

    try:
        parser.feed(html)
    except Exception:
        return []

    results = []
    seen = set()

    for block in parser.blocks:
        if len(block) < 3:
            continue

        if len(block) > 300:
            block = block[:300].rstrip() + "..."

        key = block.lower()

        if key in seen:
            continue

        seen.add(key)
        results.append(block)

        if len(results) >= limit:
            break

    return results


def extract_usernames(text: str) -> list[str]:
    if not text:
        return []

    usernames = {
        match.lower()
        for match in USERNAME_RE.findall(text)
    }

    return sorted(usernames)


def extract_name_candidates(text: str) -> list[str]:
    if not text:
        return []

    results = []
    seen = set()

    for match in NAME_CONTEXT_RE.findall(text):
        normalized = re.sub(r"\s+", " ", match).strip()
        lowered = normalized.lower()

        if lowered in NAME_STOPWORDS:
            continue

        if lowered in seen:
            continue

        seen.add(lowered)
        results.append(normalized)

    return results


def extract_social_links(links: list[str]) -> list[dict]:
    from extractors.social import extract_social_profiles
    return extract_social_profiles(links)


def _collect_json_names(value, results):
    if isinstance(value, dict):
        value_type = value.get("@type")
        author = value.get("author")

        if value_type == "Person":
            name = value.get("name")

            if isinstance(name, str) and name.strip():
                results.append(name.strip())

        if isinstance(author, dict):
            author_type = author.get("@type")

            if author_type == "Person":
                name = author.get("name")

                if isinstance(name, str) and name.strip():
                    results.append(name.strip())

        elif isinstance(author, list):
            for item in author:
                _collect_json_names(item, results)

        for item in value.values():
            _collect_json_names(item, results)

    elif isinstance(value, list):
        for item in value:
            _collect_json_names(item, results)


class JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.in_jsonld = False
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag != "script":
            return

        attributes = dict(attrs)
        script_type = attributes.get("type", "").lower()

        if script_type == "application/ld+json":
            self.in_jsonld = True
            self.current = []

    def handle_endtag(self, tag):
        if tag == "script" and self.in_jsonld:
            self.in_jsonld = False
            raw = "".join(self.current).strip()

            if raw:
                self.scripts.append(raw)

            self.current = []

    def handle_data(self, data):
        if self.in_jsonld:
            self.current.append(data)


def extract_structured_names(html: str) -> list[str]:
    parser = JsonLdParser()

    try:
        parser.feed(html)
    except Exception:
        return []

    results = []

    for raw in parser.scripts:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        _collect_json_names(data, results)

    unique = []
    seen = set()

    for name in results:
        key = name.lower()

        if key in seen:
            continue

        seen.add(key)
        unique.append(name)

    return unique