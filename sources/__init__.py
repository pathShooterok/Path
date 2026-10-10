import time
from concurrent.futures import ThreadPoolExecutor

from core.config import get_config
from sources.bing import search_bing
from sources.duckduckgo import search_duckduckgo
from sources.google import search_google

REGISTRY = {
    "duckduckgo": search_duckduckgo,
    "bing": search_bing,
    "google": search_google,
}


def _run_source(name, func, source_cfg, target, queries, delay):
    collected = []
    for index, query in enumerate(queries):
        if index and delay:
            time.sleep(delay)
        print(f"[*] {name}: {query}")
        try:
            found = func(
                query,
                limit=source_cfg.get("limit", 10),
                target=target,
                require_target_match=source_cfg.get("require_target_match", False),
            )
        except Exception as error:
            print(f"[-] {name} failed: {error}")
            found = []
        print(f"    {name} -> {len(found)} results")
        collected.extend(found)
    return collected


def run_search(target: str, queries: list[str], only: list[str] | None = None) -> list[dict]:
    cfg = get_config()["sources"]
    names = only if only else cfg["order"]
    delay = cfg.get("delay_between", 0)

    jobs = []
    for name in names:
        func = REGISTRY.get(name)
        source_cfg = cfg.get(name, {})
        if func is None:
            print(f"[-] Unknown source in config: {name}")
            continue
        if not only and not source_cfg.get("enabled", True):
            continue
        jobs.append((name, func, source_cfg))

    if not jobs:
        return []

    workers = len(jobs) if cfg.get("parallel", True) else 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_run_source, name, func, source_cfg, target, queries, delay)
            for name, func, source_cfg in jobs
        ]
        batches = [future.result() for future in futures]

    results, seen = [], set()
    for batch in batches:
        for item in batch:
            key = item["url"].rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
    return results
