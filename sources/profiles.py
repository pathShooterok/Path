"""Direct profile probing: does <platform>/<username> exist, and what does it publish?

Only platforms where "no such user" is reliably distinguishable (404 or an
explicit marker) are listed. Each probe returns the public profile HTML so the
normal extractors (email, links, metadata, identity) can run on it.
"""
import json
import re
import time

from core.config import get_config
from core.http import fetch, decode_body

# name -> url template, validity regex for the username on that platform,
# optional marker that must be present (positive) / absent (negative)
PROBES = {
    "GitHub":   {"url": "https://github.com/{u}", "valid": r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$"},
    "GitLab":   {"url": "https://gitlab.com/{u}", "valid": r"^[A-Za-z0-9_.\-]{2,255}$"},
    "Habr":     {"url": "https://habr.com/ru/users/{u}/", "valid": r"^[A-Za-z0-9_\-]{2,32}$"},
    "Keybase":  {"url": "https://keybase.io/{u}", "valid": r"^[A-Za-z0-9_]{2,16}$"},
    "DEV":      {"url": "https://dev.to/{u}", "valid": r"^[A-Za-z0-9_]{2,30}$"},
    "Pikabu":   {"url": "https://pikabu.ru/@{u}", "valid": r"^[A-Za-z0-9_.\-]{2,40}$"},
    "Telegram": {"url": "https://t.me/{u}", "valid": r"^[A-Za-z][A-Za-z0-9_]{4,31}$",
                 "present": r'class="tgme_page_title"'},
}


def _exists(name: str, spec: dict, response: dict, html: str) -> bool:
    if not response["ok"] or response["status"] != 200:
        return False
    if "present" in spec and not re.search(spec["present"], html):
        return False
    return True


def github_api(username: str) -> dict | None:
    """Public profile fields from the GitHub REST API (no auth, 60 req/h)."""
    response = fetch(
        f"https://api.github.com/users/{username}",
        headers={"Accept": "application/vnd.github+json"},
    )
    if not response["ok"]:
        return None
    try:
        return json.loads(decode_body(response))
    except json.JSONDecodeError:
        return None


def probe_profiles(username: str, platforms: list[str] | None = None) -> list[dict]:
    """Return [{platform, username, url, html}] for platforms where the profile exists."""
    cfg = get_config()["profiles"]
    names = platforms or cfg["platforms"] or list(PROBES)
    delay = get_config()["sources"].get("delay_between", 0) / 2
    found = []

    for name in names:
        spec = PROBES.get(name)
        if not spec:
            print(f"[-] Unknown profile platform in config: {name}")
            continue
        if not re.match(spec["valid"], username):
            continue  # username can't exist on this platform

        url = spec["url"].format(u=username)
        response = fetch(url)
        html = decode_body(response) if response["ok"] else ""
        exists = _exists(name, spec, response, html)
        print(f"    {name:<9} {'FOUND' if exists else '-'}"
              + ("" if exists or response["ok"] or response["status"] == 404
                 else f"  ({response['error']})"))
        if exists:
            found.append({"platform": name, "username": username,
                          "url": response["final_url"] or url, "html": html})
        if delay:
            time.sleep(delay)

    return found
