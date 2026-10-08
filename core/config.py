"""Config loading: built-in defaults <- config.json <- CLI overrides."""
import copy
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULTS = {
    "http": {
        "timeout": 10,
        "retries": 2,
        "backoff": 2.0,
        "max_response_bytes": 2 * 1024 * 1024,
        "accept_language": "en-US,en;q=0.9,ru;q=0.8",
        "user_agents": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        ],
    },
    "sources": {
        # order = priority; results are merged and deduplicated by URL
        "order": ["duckduckgo", "bing", "google"],
        "delay_between": 1.0,
        "duckduckgo": {"enabled": True, "limit": 10},
        "bing": {"enabled": True, "limit": 10, "require_target_match": False},
        # Google serves a JS-only page to non-browser clients most of the time
        "google": {"enabled": False, "limit": 10},
    },
    "trace": {
        # extra search queries; {target} is replaced. First one is the exact phrase.
        # keep queries plain: operators like "email OR contact" pull in email-finder spam
        "queries": ['"{target}"'],
        # drop search results that don't contain the target (normalised) in url/title/snippet
        "require_target_in_result": True,
        "scan_social_profiles": True,
        "max_profiles": 5,
        # minimum username match to fetch a profile: exact | normalized | partial
        "min_profile_match": "normalized",
    },
    "profiles": {
        # probe known platforms directly for <platform>/<username>
        "enabled": True,
        "platforms": ["GitHub", "GitLab", "Habr", "Keybase", "DEV", "Pikabu", "Telegram"],
        "github_api": True,
        # also try boba_1 -> boba-1 / boba1 on platforms where the exact nick is invalid or missing
        "try_variants": True,
    },
    "scan": {
        "max_linked_pages": 10,
        "follow_social_links": True,
    },
}


def _merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


_config: dict | None = None


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict:
    global _config
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        config_path = Path(path)
    else:
        # ./config.json (installed use) wins over the one next to the source tree
        cwd_config = Path.cwd() / "config.json"
        config_path = cwd_config if cwd_config.exists() else DEFAULT_CONFIG_PATH

    if config_path.exists():
        text = config_path.read_text(encoding="utf-8").strip()
        if text:
            try:
                _merge(cfg, json.loads(text))
            except json.JSONDecodeError as e:
                raise SystemExit(f"[-] Invalid JSON in {config_path}: {e}")
    elif path:
        raise SystemExit(f"[-] Config not found: {config_path}")

    # personal overrides, git-ignored: config.local.json next to config.json
    local = config_path.with_name("config.local.json")
    if not path and local.exists() and local.read_text(encoding="utf-8").strip():
        try:
            _merge(cfg, json.loads(local.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            raise SystemExit(f"[-] Invalid JSON in {local}: {e}")

    if overrides:
        _merge(cfg, overrides)

    _config = cfg
    return cfg


def get_config() -> dict:
    return _config if _config is not None else load_config()
