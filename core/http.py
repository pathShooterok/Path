import random
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.config import get_config

RETRY_STATUS_CODES = {429, 502, 503, 504}


def _headers(extra: dict | None = None) -> dict:
    cfg = get_config()["http"]
    headers = {
        "User-Agent": random.choice(cfg["user_agents"]),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": cfg["accept_language"],
    }
    if extra:
        headers.update(extra)
    return headers


def fetch(url: str, headers: dict | None = None, timeout: float | None = None) -> dict:
    cfg = get_config()["http"]
    timeout = timeout or cfg["timeout"]
    max_bytes = cfg["max_response_bytes"]
    retries = cfg["retries"]
    backoff = cfg["backoff"]

    result = {
        "ok": False, "status": None, "final_url": url,
        "headers": {}, "data": b"", "truncated": False, "error": None,
    }

    if not url.startswith(("http://", "https://")):
        result["error"] = "Only http:// and https:// URLs are supported"
        return result

    request = Request(url, headers=_headers(headers))

    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                data = response.read(max_bytes + 1)
                result.update(
                    ok=True,
                    status=response.status,
                    final_url=response.geturl(),
                    headers=response.headers,
                    truncated=len(data) > max_bytes,
                    data=data[:max_bytes],
                    error=None,
                )
                return result
        except HTTPError as e:
            result["status"] = e.code
            result["error"] = f"HTTP {e.code}: {e.reason}"
            if e.code in RETRY_STATUS_CODES and attempt < retries:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                wait = int(retry_after) if retry_after and retry_after.isdigit() \
                    else backoff * (2 ** attempt)
                time.sleep(min(wait, 30))
                continue
            return result
        except (URLError, TimeoutError, socket.timeout) as e:
            result["error"] = str(getattr(e, "reason", e))
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
                continue
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

    return result


def decode_body(result: dict) -> str:
    data = result.get("data") or b""
    charset = None
    headers = result.get("headers")
    if headers is not None and hasattr(headers, "get_content_charset"):
        charset = headers.get_content_charset()
    try:
        return data.decode(charset or "utf-8", errors="ignore")
    except LookupError:
        return data.decode("utf-8", errors="ignore")
