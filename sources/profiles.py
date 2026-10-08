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
    # gitlab.com blocks scripted page requests (403); the public users API does not
    "GitLab":   {"url": "https://gitlab.com/{u}", "valid": r"^[A-Za-z0-9_.\-]{2,255}$",
                 "api": "https://gitlab.com/api/v4/users?username={u}"},
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


def username_variants(username: str) -> list[str]:
    """The nick itself plus common platform-driven spellings (boba_1 -> boba-1, boba1)."""
    variants = [username]
    for v in (username.replace("_", "-"), username.replace("_", "").replace("-", "")):
        if v and v not in variants:
            variants.append(v)
    return variants


def _probe_one(name: str, spec: dict, username: str) -> dict | None:
    """Return a profile dict if it exists, else None. Prints one status line."""
    if "api" in spec:
        response = fetch(spec["api"].format(u=username))
        status = response["status"]
        try:
            users = json.loads(decode_body(response)) if response["ok"] else []
        except json.JSONDecodeError:
            users = []
        match = next((u for u in users if u.get("username", "").lower() == username.lower()), None)
        label = "FOUND" if match else ("-" if response["ok"] or status == 404
                                       else f"?  ({response['error']})")
        print(f"    {name:<9} {username}: {label}")
        if not match:
            return None
        return {"platform": name, "username": match["username"], "html": "",
                "url": match.get("web_url") or spec["url"].format(u=username),
                "name": match.get("name", "")}

    url = spec["url"].format(u=username)
    response = fetch(url)
    html = decode_body(response) if response["ok"] else ""
    exists = _exists(name, spec, response, html)
    label = "FOUND" if exists else ("-" if response["ok"] or response["status"] == 404
                                    else f"?  ({response['error']})")
    print(f"    {name:<9} {username}: {label}")
    if not exists:
        return None
    return {"platform": name, "username": username,
            "url": response["final_url"] or url, "html": html, "name": ""}


def probe_profiles(username: str, platforms: list[str] | None = None) -> list[dict]:
    """Return [{platform, username, url, html, name, variant}] for profiles that exist.

    variant=True means the profile matched a spelling variant, not the exact nick.
    """
    cfg = get_config()["profiles"]
    names = platforms or cfg["platforms"] or list(PROBES)
    delay = get_config()["sources"].get("delay_between", 0) / 2
    variants = username_variants(username) if cfg.get("try_variants", True) else [username]
    found = []

    for name in names:
        spec = PROBES.get(name)
        if not spec:
            print(f"[-] Unknown profile platform in config: {name}")
            continue

        tried = [v for v in variants if re.match(spec["valid"], v)]
        if not tried:
            print(f"    {name:<9} skipped (username not valid on this platform)")
            continue

        for candidate in tried:
            profile = _probe_one(name, spec, candidate)
            if profile:
                profile["variant"] = candidate != username
                found.append(profile)
                break  # first hit wins; exact nick is tried first
            if delay:
                time.sleep(delay)

    return found
