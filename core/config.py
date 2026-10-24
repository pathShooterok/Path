import copy
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULTS = {
    "http": {
        "timeout": 10,
        "retries": 2,
        "backoff": 2.0,
        "max_response_bytes": 2 * 1024 * 1024,
        "max_requests_per_run": 100,
        "max_total_response_bytes": 20 * 1024 * 1024,
        "max_run_seconds": 120,
        "accept_language": "en-US,en;q=0.9,ru;q=0.8",
        "user_agents": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        ],
    },
    "cache": {
        "enabled": True,
        "ttl": 3600,
        "dir": ".path_cache",
    },
    "sources": {
        "order": ["duckduckgo", "bing", "google"],
        "delay_between": 1.0,
        "parallel": True,
        "duckduckgo": {"enabled": True, "limit": 10},
        "bing": {"enabled": True, "limit": 10, "require_target_match": False},
        "google": {"enabled": False, "limit": 10},
    },
    "trace": {
        "queries": ['"{target}"'],
        "require_target_in_result": True,
        "scan_social_profiles": True,
        "max_profiles": 5,
        "min_profile_match": "normalized",
        "ignore_domains": [
            "dictionary.com", "dictionary.cambridge.org", "merriam-webster.com",
            "thefreedictionary.com", "collinsdictionary.com", "wiktionary.org",
            "oxfordlearnersdictionaries.com", "lexico.com", "vocabulary.com",
            "thesaurus.com", "wordreference.com", "slovar.cc", "gramota.ru"
        ],
    },
    "profiles": {
        "enabled": True,
        "platforms": ["GitHub", "GitLab", "Habr", "Keybase", "DEV", "Pikabu", "Telegram",
                      "HackerNews", "DockerHub", "Bluesky", "Lichess", "Chess.com",
                      "Mastodon", "Gravatar"],
        "github_api": True,
        "workers": 6,
        "try_variants": True,
    },
    "breaches": {
        "enabled": False,
        "max_emails": 3,
        "only_personal": True,
    },
    "cleanup": {
        "enabled": True,
        "drop_test_emails": True,
        "drop_junk_text": True,
        "max_value_length": 300,
    },
    "scan": {
        "max_linked_pages": 10,
        "follow_social_links": True,
        "discord_invites": True,
        "max_discord_invites": 3,
    },
}


def _merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


NUMBERS = {
    ("http", "timeout"): (float, 0, False),
    ("http", "retries"): (int, 0, True),
    ("http", "backoff"): (float, 0, True),
    ("http", "max_response_bytes"): (int, 1, True),
    ("http", "max_requests_per_run"): (int, 1, True),
    ("http", "max_total_response_bytes"): (int, 1, True),
    ("http", "max_run_seconds"): (float, 0, False),
    ("cache", "ttl"): (float, 0, True),
    ("sources", "delay_between"): (float, 0, True),
    ("trace", "max_profiles"): (int, 0, True),
    ("profiles", "workers"): (int, 1, True),
    ("scan", "max_linked_pages"): (int, 0, True),
    ("scan", "max_discord_invites"): (int, 0, True),
    ("breaches", "max_emails"): (int, 0, True),
    ("cleanup", "max_value_length"): (int, 0, True),
}

FLAGS = [
    ("cache", "enabled"), ("sources", "parallel"), ("trace", "require_target_in_result"),
    ("trace", "scan_social_profiles"), ("profiles", "enabled"), ("profiles", "github_api"),
    ("profiles", "try_variants"), ("scan", "follow_social_links"), ("scan", "discord_invites"),
    ("breaches", "enabled"), ("breaches", "only_personal"), ("cleanup", "enabled"),
    ("cleanup", "drop_test_emails"), ("cleanup", "drop_junk_text"),
]

LISTS = [
    ("sources", "order"), ("trace", "queries"), ("trace", "ignore_domains"),
    ("profiles", "platforms"), ("http", "user_agents"),
]

MATCH_LEVELS = ("exact", "normalized", "partial")


def _number_ok(value, kind, minimum, inclusive) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if kind is int and not isinstance(value, int):
        return False
    return value >= minimum if inclusive else value > minimum


def validate_config(cfg: dict) -> list[str]:
    problems = []
    for (section, key), (kind, minimum, inclusive) in NUMBERS.items():
        value = cfg.get(section, {}).get(key)
        if not _number_ok(value, kind, minimum, inclusive):
            rule = f">= {minimum}" if inclusive else f"> {minimum}"
            expected = "a whole number" if kind is int else "a number"
            problems.append(f"{section}.{key} must be {expected} {rule}, got {value!r}")
    for section, key in FLAGS:
        if not isinstance(cfg.get(section, {}).get(key), bool):
            problems.append(f"{section}.{key} must be true or false, got {cfg.get(section, {}).get(key)!r}")
    for section, key in LISTS:
        value = cfg.get(section, {}).get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            problems.append(f"{section}.{key} must be a list of strings")
    if not cfg["trace"]["queries"]:
        problems.append("trace.queries must contain at least one query")
    if cfg["trace"].get("min_profile_match") not in MATCH_LEVELS:
        problems.append(f"trace.min_profile_match must be one of {', '.join(MATCH_LEVELS)}")
    return problems


def _warn_unknown(user_cfg: dict, source: str) -> None:
    for key in user_cfg:
        if key not in DEFAULTS:
            print(f"[!] {source}: unknown config section '{key}' (ignored)", file=sys.stderr)


_config: dict | None = None


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict:
    global _config
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        config_path = Path(path)
    else:
        cwd_config = Path.cwd() / "config.json"
        config_path = cwd_config if cwd_config.exists() else DEFAULT_CONFIG_PATH

    if config_path.exists():
        text = config_path.read_text(encoding="utf-8").strip()
        if text:
            try:
                user_cfg = json.loads(text)
            except json.JSONDecodeError as e:
                raise SystemExit(f"[-] Invalid JSON in {config_path}: {e}")
            if not isinstance(user_cfg, dict):
                raise SystemExit(f"[-] {config_path} must contain a JSON object")
            _warn_unknown(user_cfg, config_path.name)
            _merge(cfg, user_cfg)
    elif path:
        raise SystemExit(f"[-] Config not found: {config_path}")

    local = config_path.with_name("config.local.json")
    if not path and local.exists() and local.read_text(encoding="utf-8").strip():
        try:
            _merge(cfg, json.loads(local.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            raise SystemExit(f"[-] Invalid JSON in {local}: {e}")

    if overrides:
        _merge(cfg, overrides)

    problems = validate_config(cfg)
    if problems:
        raise SystemExit("[-] Invalid configuration:\n" + "\n".join(f"    - {p}" for p in problems))

    _config = cfg
    return cfg


def get_config() -> dict:
    return _config if _config is not None else load_config()
