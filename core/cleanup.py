import re
from urllib.parse import urlparse

from core.config import get_config
from extractors.social import parse_social_url

RANK = {"high": 3, "medium": 2, "low": 1}

PLACEHOLDER_DOMAINS = {"example.com", "example.org", "example.net", "test.com", "domain.com",
                       "yourdomain.com", "email.com", "mydomain.com"}

PLACEHOLDER_LOCALS = {"example", "test", "user", "name", "email", "your", "yourname", "john.doe",
                      "username", "mail"}

TITLE_KINDS = {"title", "og_title", "linked_title", "linked_og_title",
               "description", "og_description", "linked_description", "linked_og_description"}

JUNK_TEXT = {
    "login", "log in", "sign in", "sign up", "register", "home", "homepage", "index",
    "404", "403", "not found", "page not found", "access denied", "forbidden", "error",
    "just a moment", "just a moment...", "attention required", "attention required! | cloudflare",
    "redirecting", "redirecting...", "loading", "loading...", "untitled", "document",
    "are you a robot?", "captcha", "please wait", "please wait...", "security check",
    "вход", "войти", "регистрация", "страница не найдена", "ошибка", "доступ запрещён",
    "доступ запрещен", "загрузка", "загрузка...",
}


BOILERPLATE = [re.compile(x, re.I) for x in (
    r"has \d+ repositories available\. follow their code on github",
    r"^все (публикации|посты)",
    r"все посты пользователя",
    r"^профиль .+ на пикабу$",
    r"^.+ - overview$",
    r"подпишитесь на ленту",
)]


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _url_key(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    path = parsed.path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{host}{path}{query}"


def _family(kind: str) -> str:
    return kind[7:] if kind.startswith("linked_") else kind


def _is_placeholder_email(finding) -> bool:
    if finding.classification == "test":
        return True
    local, _, domain = finding.value.lower().partition("@")
    return domain in PLACEHOLDER_DOMAINS or (local in PLACEHOLDER_LOCALS and domain.endswith(".example"))


def _is_junk(finding) -> bool:
    value = _squash(finding.value)
    if not value:
        return True
    if finding.kind in TITLE_KINDS:
        if len(value) < 2 or value.lower() in JUNK_TEXT:
            return True
        return any(rx.search(value) for rx in BOILERPLATE)
    if finding.kind in ("name", "linked_name", "linked_username"):
        owner = parse_social_url(finding.source) if finding.source else None
        if owner and owner["username"].lower() == value.lower():
            return True
    if finding.kind in ("og_url", "linked_og_url") and finding.source:
        return _url_key(value).lower() == _url_key(finding.source).lower()
    return False


def _key(finding):
    kind = finding.kind
    if kind in ("social", "linked_social"):
        parsed = parse_social_url(finding.value.split(": ", 1)[-1])
        if parsed:
            return ("social", parsed["platform"], parsed["username"].lower())
    if kind == "email":
        return ("email", finding.value.lower())
    value = _squash(finding.value)
    if value.startswith(("http://", "https://")):
        return (_family(kind), _url_key(value), "")
    return (_family(kind), value.lower(), finding.source if kind in ("web_result",) else "")


def _better(candidate, current) -> bool:
    cand = RANK.get(candidate.confidence, 0)
    cur = RANK.get(current.confidence, 0)
    if cand != cur:
        return cand > cur
    return candidate.kind == "social" and current.kind != "social"


def clean_report(report) -> dict:
    cfg = get_config().get("cleanup", {})
    stats = {"junk": 0, "placeholder_emails": 0, "duplicates": 0}
    if not cfg.get("enabled", True):
        return stats

    limit = cfg.get("max_value_length", 300)
    kept: dict[tuple, dict] = {}
    order = []

    for finding in report.findings:
        if finding.kind in ("correlation", "correlation_unmatched"):
            order.append(("raw", finding))
            continue
        if cfg.get("drop_test_emails", True) and finding.kind == "email" \
                and _is_placeholder_email(finding):
            stats["placeholder_emails"] += 1
            continue
        if cfg.get("drop_junk_text", True) and _is_junk(finding):
            stats["junk"] += 1
            continue

        finding.value = _squash(finding.value) if finding.kind != "email" else finding.value.strip()
        if limit and len(finding.value) > limit:
            finding.value = finding.value[: limit - 1].rstrip() + "…"

        key = _key(finding)
        entry = kept.get(key)
        if entry is None:
            entry = {"finding": finding, "extra": 0}
            kept[key] = entry
            order.append(("key", key))
            continue

        entry["extra"] += 1
        stats["duplicates"] += 1
        if _better(finding, entry["finding"]):
            entry["finding"] = finding

    cleaned = []
    for tag, item in order:
        if tag == "raw":
            cleaned.append(item)
            continue
        entry = kept[item]
        finding = entry["finding"]
        if entry["extra"]:
            finding.evidence = f"{finding.evidence} (seen {entry['extra'] + 1} times)"
        cleaned.append(finding)

    report.findings = cleaned
    return stats
