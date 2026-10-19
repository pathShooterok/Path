import json
import time
from urllib.parse import quote

from core.config import get_config
from core.http import fetch, decode_body

ENDPOINT = "https://api.xposedornot.com/v1/breach-analytics?email={email}"


def _items(data) -> list[dict]:
    exposed = data.get("ExposedBreaches") if isinstance(data, dict) else None
    details = exposed.get("breaches_details") if isinstance(exposed, dict) else None
    return [item for item in (details or []) if isinstance(item, dict)]


def _text(value) -> str:
    return str(value).strip() if isinstance(value, (str, int, float)) else ""


def check_email(email: str) -> dict:
    response = fetch(ENDPOINT.format(email=quote(email, safe="@")))
    if response["status"] == 429:
        return {"status": "limited", "breaches": []}
    if response["status"] == 404:
        return {"status": "none", "breaches": []}
    if not response["ok"]:
        return {"status": "error", "breaches": [], "error": response["error"]}
    try:
        data = json.loads(decode_body(response))
    except json.JSONDecodeError:
        return {"status": "error", "breaches": [], "error": "bad response"}

    breaches = []
    for item in _items(data):
        name = _text(item.get("breach"))
        if not name:
            continue
        classes = [c.strip() for c in _text(item.get("xposed_data")).split(";") if c.strip()]
        breaches.append({
            "name": name,
            "domain": _text(item.get("domain")),
            "year": _text(item.get("xposed_date")),
            "classes": classes,
            "records": item.get("xposed_records") if isinstance(item.get("xposed_records"), int) else None,
        })
    return {"status": "found" if breaches else "none", "breaches": breaches}


def check_emails(emails: list[str]) -> dict[str, dict]:
    results = {}
    for index, email in enumerate(emails):
        if index:
            time.sleep(0.6)
        results[email] = check_email(email)
        if results[email]["status"] == "limited":
            break
    return results


def enabled() -> bool:
    return bool(get_config().get("breaches", {}).get("enabled", False))
