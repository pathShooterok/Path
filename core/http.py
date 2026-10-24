import ipaddress
import random
import socket
import threading
import time
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from core import cache
from core.config import get_config

RETRY_STATUS_CODES = {429, 502, 503, 504}
_budget_lock = threading.Lock()
_budget_active = False
_budget_requests = 0
_budget_bytes = 0
_budget_deadline = 0.0
_budget_max_requests = 0
_budget_max_bytes = 0


def request_budget(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        global _budget_active, _budget_requests, _budget_bytes
        global _budget_deadline, _budget_max_requests, _budget_max_bytes
        cfg = get_config()["http"]
        with _budget_lock:
            _budget_active = True
            _budget_requests = 0
            _budget_bytes = 0
            _budget_deadline = time.monotonic() + max(1, int(cfg.get("max_run_seconds", 120)))
            _budget_max_requests = max(1, int(cfg.get("max_requests_per_run", 100)))
            _budget_max_bytes = max(1, int(cfg.get("max_total_response_bytes", 20 * 1024 * 1024)))
        try:
            return function(*args, **kwargs)
        finally:
            with _budget_lock:
                requests = _budget_requests
                response_bytes = _budget_bytes
                max_requests = _budget_max_requests
                max_bytes = _budget_max_bytes
                _budget_active = False
            print(f"[*] Network budget used: {requests}/{max_requests} requests, "
                  f"{response_bytes}/{max_bytes} response bytes")
    return wrapped


def _take_request_slot() -> str | None:
    global _budget_requests
    with _budget_lock:
        if not _budget_active:
            return None
        if time.monotonic() >= _budget_deadline:
            return "Maximum scan time reached"
        if _budget_requests >= _budget_max_requests:
            return "Maximum HTTP requests per scan reached"
        _budget_requests += 1
    return None


def _request_timeout(timeout: float) -> float:
    with _budget_lock:
        if not _budget_active:
            return timeout
        remaining = _budget_deadline - time.monotonic()
        return min(timeout, max(0.001, remaining))


def _reserve_response_bytes(limit: int) -> int:
    global _budget_bytes
    with _budget_lock:
        if not _budget_active:
            return limit
        remaining = _budget_max_bytes - _budget_bytes
        if remaining <= 0:
            return 0
        reserved = min(limit, remaining)
        _budget_bytes += reserved
        return reserved


def _release_response_bytes(reserved: int, used: int = 0) -> None:
    global _budget_bytes
    with _budget_lock:
        if _budget_active:
            _budget_bytes -= max(0, reserved - used)


def _validate_public_url(url: str) -> str | None:
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return "Only http:// and https:// URLs are supported"
        if not parsed.hostname or parsed.username is not None or parsed.password is not None:
            return "URL must have a hostname and must not include credentials"
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError:
        return "Invalid URL"

    host = parsed.hostname.rstrip(".")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        addresses = [literal]
    else:
        try:
            ascii_host = host.encode("idna").decode("ascii")
            addresses = [
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(ascii_host, port, type=socket.SOCK_STREAM)
            ]
        except (UnicodeError, OSError, ValueError):
            return "Could not resolve URL hostname"

    if not addresses or any(not address.is_global for address in addresses):
        return "Requests to non-public IP addresses are not allowed"
    return None


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        error = _validate_public_url(newurl)
        if error:
            raise URLError(error)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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

    error = _validate_public_url(url)
    if error:
        result["error"] = error
        return result

    cached = cache.load(url, headers)
    if cached is not None:
        return cached

    request = Request(url, headers=_headers(headers))
    opener = build_opener(_SafeRedirectHandler())

    for attempt in range(retries + 1):
        byte_limit = _reserve_response_bytes(max_bytes)
        if not byte_limit:
            result["error"] = "Maximum response bytes per scan reached"
            return result
        error = _take_request_slot()
        if error:
            _release_response_bytes(byte_limit)
            result["error"] = error
            return result
        reserved = byte_limit
        try:
            with opener.open(request, timeout=_request_timeout(timeout)) as response:
                data = response.read(byte_limit + 1)
                truncated = len(data) > byte_limit
                data = data[:byte_limit]
                _release_response_bytes(reserved, len(data))
                reserved = 0
                result.update(
                    ok=True,
                    status=response.status,
                    final_url=response.geturl(),
                    headers=response.headers,
                    truncated=truncated,
                    data=data,
                    error=None,
                )
                cache.store(url, headers, result)
                return result
        except HTTPError as e:
            _release_response_bytes(reserved)
            reserved = 0
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
            _release_response_bytes(reserved)
            reserved = 0
            result["error"] = str(getattr(e, "reason", e))
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
                continue
            return result
        except Exception as e:
            _release_response_bytes(reserved)
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
