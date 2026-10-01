import json
from pathlib import Path


DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "email_filters.json"
)


def load_filters() -> dict:
    if not DATA_FILE.exists():
        return {
            "test_domains": [],
            "technical_prefixes": [],
        }

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


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