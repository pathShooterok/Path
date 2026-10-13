import base64
import hashlib
import json
import os
import threading
import time
from email import message_from_string
from pathlib import Path

from core.blocks import is_block_page
from core.config import get_config


def _settings() -> dict:
    return get_config()["cache"]


def _path(url: str, headers: dict | None) -> Path:
    material = url + "\n" + json.dumps(headers or {}, sort_keys=True)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return Path(_settings()["dir"]) / digest[:2] / f"{digest}.json"


def load(url: str, headers: dict | None = None) -> dict | None:
    settings = _settings()
    if not settings["enabled"]:
        return None
    try:
        payload = json.loads(_path(url, headers).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - payload.get("stored_at", 0) > settings["ttl"]:
        return None
    return {
        "ok": True,
        "status": payload["status"],
        "final_url": payload["final_url"],
        "headers": message_from_string(payload["headers"]),
        "data": base64.b64decode(payload["data"]),
        "truncated": False,
        "error": None,
        "cached": True,
    }


def store(url: str, headers: dict | None, result: dict) -> None:
    if not _settings()["enabled"]:
        return
    if not result["ok"] or result["status"] != 200 or result["truncated"]:
        return
    data = result["data"]
    if is_block_page(data[:20_000].decode("utf-8", errors="ignore")):
        return
    header_text = "".join(f"{key}: {value}\n" for key, value in result["headers"].items())
    payload = {
        "stored_at": time.time(),
        "status": result["status"],
        "final_url": result["final_url"],
        "headers": header_text,
        "data": base64.b64encode(data).decode("ascii"),
    }
    path = _path(url, headers)
    temp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(temp, path)
    except OSError:
        try:
            temp.unlink()
        except OSError:
            pass
