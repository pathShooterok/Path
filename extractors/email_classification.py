import json
from pathlib import Path


DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "core"
    / "data"
    / "email_filters.json"
)

_FILTERS_CACHE: dict | None = None


def load_filters() -> dict:
    global _FILTERS_CACHE
    if _FILTERS_CACHE is not None:
        return _FILTERS_CACHE

    if not DATA_FILE.exists():
        _FILTERS_CACHE = {
            "test_domains": [],
            "technical_prefixes": [],
        }
        return _FILTERS_CACHE

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        _FILTERS_CACHE = json.load(file)
    return _FILTERS_CACHE


def classify_email(email: str) -> str:
    email = email.strip().lower()

    if "@" not in email:
        return "invalid"

    local_part, domain = email.rsplit("@", 1)

    filters = load_filters()

    if domain in filters.get("test_domains", []):
        return "test"

    prefixes = filters.get(
        "technical_prefixes",
        [],
    )

    if local_part in prefixes:
        return "technical"

    return "personal_candidate"