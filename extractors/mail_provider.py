import json
from pathlib import Path


DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "mail_providers.json"
)


def load_providers() -> dict[str, list[str]]:
    if not DATA_FILE.exists():
        return {}

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def identify_provider(email: str) -> str:
    email = email.strip().lower()

    if "@" not in email:
        return "unknown"

    domain = email.rsplit("@", 1)[1]

    providers = load_providers()

    for provider, domains in providers.items():
        if domain in domains:
            return provider

    return "custom"