import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

from core.config import get_config
from core.http import fetch, decode_body

PROBES = {
    "GitHub":   {"url": "https://github.com/{u}", "valid": r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$"},
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
    variants = [username]
    for v in (username.replace("_", "-"), username.replace("_", "").replace("-", "")):
        if v and v not in variants:
            variants.append(v)
    return variants


def _probe_one(name: str, spec: dict, username: str):
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
        if not match:
            return None, label
        return {"platform": name, "username": match["username"], "html": "",
                "url": match.get("web_url") or spec["url"].format(u=username),
                "name": match.get("name", "")}, label

    url = spec["url"].format(u=username)
    response = fetch(url)
    html = decode_body(response) if response["ok"] else ""
    exists = _exists(name, spec, response, html)
    label = "FOUND" if exists else ("-" if response["ok"] or response["status"] == 404
                                    else f"?  ({response['error']})")
    if not exists:
        return None, label
    return {"platform": name, "username": username,
            "url": response["final_url"] or url, "html": html, "name": ""}, label


def _probe_platform(name: str, spec: dict, username: str, variants: list[str], delay: float):
    tried = [v for v in variants if re.match(spec["valid"], v)]
    if not tried:
        return [f"    {name:<9} skipped (username not valid on this platform)"], None

    lines = []
    for candidate in tried:
        profile, label = _probe_one(name, spec, candidate)
        lines.append(f"    {name:<9} {candidate}: {label}")
        if profile:
            profile["variant"] = candidate != username
            return lines, profile
        if delay:
            time.sleep(delay)
    return lines, None


def probe_profiles(username: str, platforms: list[str] | None = None) -> list[dict]:
    cfg = get_config()["profiles"]
    names = platforms or cfg["platforms"] or list(PROBES)
    delay = get_config()["sources"].get("delay_between", 0) / 2
    variants = username_variants(username) if cfg.get("try_variants", True) else [username]

    jobs = []
    for name in names:
        spec = PROBES.get(name)
        if not spec:
            print(f"[-] Unknown profile platform in config: {name}")
            continue
        jobs.append((name, spec))

    if not jobs:
        return []

    workers = max(1, min(cfg.get("workers", 6), len(jobs)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_probe_platform, name, spec, username, variants, delay)
            for name, spec in jobs
        ]
        outcomes = [future.result() for future in futures]

    found = []
    for lines, profile in outcomes:
        for line in lines:
            print(line)
        if profile:
            found.append(profile)
    return found
