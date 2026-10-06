import json
from pathlib import Path


DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "mail_providers.json"
)

_PROVIDERS_CACHE: dict[str, list[str]] | None = None


def load_providers() -> dict[str, list[str]]:
    global _PROVIDERS_CACHE
    if _PROVIDERS_CACHE is not None:
        return _PROVIDERS_CACHE

    if not DATA_FILE.exists():
        _PROVIDERS_CACHE = {}
        return _PROVIDERS_CACHE

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        _PROVIDERS_CACHE = json.load(file)
    return _PROVIDERS_CACHE


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