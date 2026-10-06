"""Search source registry. Config decides which run and in what order."""
import time

from core.config import get_config
from sources.bing import search_bing
from sources.duckduckgo import search_duckduckgo
from sources.google import search_google

REGISTRY = {
    "duckduckgo": search_duckduckgo,
    "bing": search_bing,
    "google": search_google,
}


def run_search(target: str, queries: list[str], only: list[str] | None = None) -> list[dict]:
    """Run every enabled source for every query; return results deduped by URL."""
    cfg = get_config()["sources"]
    names = only if only else cfg["order"]
    delay = cfg.get("delay_between", 0)

    results, seen, first = [], set(), True

    for name in names:
        func = REGISTRY.get(name)
        source_cfg = cfg.get(name, {})
        if func is None:
            print(f"[-] Unknown source in config: {name}")
            continue
        if not only and not source_cfg.get("enabled", True):
            continue

        for query in queries:
            if not first and delay:
                time.sleep(delay)
            first = False

            print(f"[*] {name}: {query}")
            found = func(
                query,
                limit=source_cfg.get("limit", 10),
                target=target,
                require_target_match=source_cfg.get("require_target_match", False),
            )
            print(f"    -> {len(found)} results")

            for item in found:
                key = item["url"].rstrip("/").lower()
                if key in seen:
                    continue
                seen.add(key)
                results.append(item)

    return results
