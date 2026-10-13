import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

from core.config import get_config
from core.http import fetch, decode_body

PAGE_PROBES = {
    "GitHub": {"url": "https://github.com/{u}", "valid": r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$"},
    "Habr": {"url": "https://habr.com/ru/users/{u}/", "valid": r"^[A-Za-z0-9_\-]{2,32}$"},
    "DEV": {"url": "https://dev.to/{u}", "valid": r"^[A-Za-z0-9_]{2,30}$"},
    "Pikabu": {"url": "https://pikabu.ru/@{u}", "valid": r"^[A-Za-z0-9_.\-]{2,40}$"},
    "Telegram": {"url": "https://t.me/{u}", "valid": r"^[A-Za-z][A-Za-z0-9_]{4,31}$",
                 "present": r'class="tgme_page_title"'},
}

API_PROBES = {
    "GitLab": {
        "api": "https://gitlab.com/api/v4/users?username={u}",
        "url": "https://gitlab.com/{u}",
        "valid": r"^[A-Za-z0-9_.\-]{2,255}$",
        "kind": "list_match",
        "fields": {"name": ["name"]},
        "url_key": "web_url",
    },
    "Keybase": {
        "api": "https://keybase.io/_/api/1.0/user/lookup.json?usernames={u}&fields=basics,profile,proofs_summary",
        "url": "https://keybase.io/{u}",
        "valid": r"^[A-Za-z0-9_]{2,16}$",
        "kind": "keybase",
    },
    "HackerNews": {
        "api": "https://hacker-news.firebaseio.com/v0/user/{u}.json",
        "url": "https://news.ycombinator.com/user?id={u}",
        "valid": r"^[A-Za-z0-9_-]{2,15}$",
        "require": "id",
        "fields": {"bio": ["about"]},
    },
    "DockerHub": {
        "api": "https://hub.docker.com/v2/users/{u}/",
        "url": "https://hub.docker.com/u/{u}",
        "valid": r"^[a-z0-9]{4,30}$",
        "require": "id",
        "fields": {"name": ["full_name"], "location": ["location"], "company": ["company"],
                   "website": ["profile_url"], "email": ["gravatar_email"]},
    },
    "Bluesky": {
        "api": "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={u}.bsky.social",
        "url": "https://bsky.app/profile/{u}.bsky.social",
        "valid": r"^[a-z0-9](?:[a-z0-9-]{1,16}[a-z0-9])$",
        "require": "did",
        "fields": {"name": ["displayName"], "bio": ["description"]},
    },
    "Lichess": {
        "api": "https://lichess.org/api/user/{u}",
        "url": "https://lichess.org/@/{u}",
        "valid": r"^[A-Za-z0-9][A-Za-z0-9_-]{1,29}$",
        "require": "id",
        "fields": {"name": ["profile.realName"], "bio": ["profile.bio", "profile.links"],
                   "location": ["profile.location"]},
    },
    "Chess.com": {
        "api": "https://api.chess.com/pub/player/{u}",
        "url": "https://www.chess.com/member/{u}",
        "valid": r"^[A-Za-z0-9_-]{3,25}$",
        "require": "username",
        "fields": {"name": ["name"], "location": ["location"]},
    },
    "Codeberg": {
        "api": "https://codeberg.org/api/v1/users/{u}",
        "url": "https://codeberg.org/{u}",
        "valid": r"^[A-Za-z0-9_.-]{1,40}$",
        "require": "login",
        "fields": {"name": ["full_name"], "bio": ["description"], "website": ["website"],
                   "location": ["location"], "email": ["email"]},
    },
}

PROBES = {**PAGE_PROBES, **API_PROBES}

DEFAULT_ORDER = [
    "GitHub", "GitLab", "Habr", "Keybase", "DEV", "Pikabu", "Telegram",
    "HackerNews", "DockerHub", "Bluesky", "Lichess", "Chess.com", "Codeberg",
]


def _dig(data, path: str):
    for part in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


def extract_fields(mapping: dict, data) -> dict:
    fields = {}
    for key, paths in mapping.items():
        values = []
        for path in paths:
            value = _dig(data, path)
            if isinstance(value, (str, int, float)) and str(value).strip():
                values.append(str(value).strip())
        if values:
            fields[key] = "\n".join(values)
    return fields


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


def _api_label(response: dict, found: bool) -> str:
    if found:
        return "FOUND"
    if response["ok"] or response["status"] in (400, 404):
        return "-"
    return f"?  ({response['error']})"


def _parse_keybase(data, username: str):
    if not isinstance(data, dict) or (data.get("status") or {}).get("code") != 0:
        return None
    them = [item for item in (data.get("them") or []) if isinstance(item, dict)]
    if not them:
        return None
    user = them[0]
    basics = user.get("basics") or {}
    if str(basics.get("username", "")).lower() != username.lower():
        return None
    fields = extract_fields(
        {"name": ["full_name"], "bio": ["bio"], "location": ["location"]},
        user.get("profile") or {},
    )
    proofs = []
    for proof in ((user.get("proofs_summary") or {}).get("all") or []):
        link = proof.get("service_url")
        if isinstance(link, str) and link.startswith(("http://", "https://")):
            proofs.append(link)
    return {"username": basics.get("username", username), "fields": fields, "proofs": proofs}


def _probe_api(name: str, spec: dict, username: str):
    response = fetch(spec["api"].format(u=username))
    data = None
    if response["ok"]:
        try:
            data = json.loads(decode_body(response))
        except json.JSONDecodeError:
            data = None

    kind = spec.get("kind", "object")
    profile = None

    if kind == "keybase":
        parsed = _parse_keybase(data, username)
        if parsed:
            profile = {"platform": name, "username": parsed["username"],
                       "url": spec["url"].format(u=parsed["username"]), "html": "",
                       "fields": parsed["fields"], "proofs": parsed["proofs"]}

    elif kind == "list_match":
        users = data if isinstance(data, list) else []
        match = next((u for u in users
                      if isinstance(u, dict) and str(u.get("username", "")).lower() == username.lower()), None)
        if match:
            profile = {"platform": name, "username": match["username"],
                       "url": match.get(spec.get("url_key", "")) or spec["url"].format(u=username),
                       "html": "", "fields": extract_fields(spec.get("fields", {}), match), "proofs": []}

    else:
        if isinstance(data, dict) and _dig(data, spec.get("require", "")) not in (None, "", [], {}):
            profile = {"platform": name, "username": username,
                       "url": spec["url"].format(u=username), "html": "",
                       "fields": extract_fields(spec.get("fields", {}), data), "proofs": []}

    return profile, _api_label(response, profile is not None)


def _probe_page(name: str, spec: dict, username: str):
    url = spec["url"].format(u=username)
    response = fetch(url)
    html = decode_body(response) if response["ok"] else ""
    exists = _exists(name, spec, response, html)
    if not exists:
        return None, _api_label(response, False)
    return {"platform": name, "username": username, "url": response["final_url"] or url,
            "html": html, "fields": {}, "proofs": []}, "FOUND"


def _probe_one(name: str, spec: dict, username: str):
    if "api" in spec:
        return _probe_api(name, spec, username)
    return _probe_page(name, spec, username)


def _probe_platform(name: str, spec: dict, username: str, variants: list[str], delay: float):
    tried = [v for v in variants if re.match(spec["valid"], v)]
    if not tried:
        return [f"    {name:<10} skipped (username not valid on this platform)"], None

    lines = []
    for candidate in tried:
        profile, label = _probe_one(name, spec, candidate)
        lines.append(f"    {name:<10} {candidate}: {label}")
        if profile:
            profile["variant"] = candidate != username
            return lines, profile
        if delay:
            time.sleep(delay)
    return lines, None


def probe_profiles(username: str, platforms: list[str] | None = None) -> list[dict]:
    cfg = get_config()["profiles"]
    names = platforms or cfg["platforms"] or DEFAULT_ORDER
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
