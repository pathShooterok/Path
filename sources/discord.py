import json
import re

from core.config import get_config
from core.http import fetch, decode_body

CODE_RE = re.compile(r"^[A-Za-z0-9\-]{2,32}$")


def invite_info(code: str) -> dict | None:
    if not CODE_RE.match(code):
        return None
    response = fetch(f"https://discord.com/api/v10/invites/{code}?with_counts=true")
    if not response["ok"]:
        return None
    try:
        data = json.loads(decode_body(response))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("code"):
        return None

    guild = data.get("guild") if isinstance(data.get("guild"), dict) else {}
    inviter = data.get("inviter") if isinstance(data.get("inviter"), dict) else {}
    return {
        "code": data["code"],
        "server": guild.get("name"),
        "description": guild.get("description"),
        "members": data.get("approximate_member_count"),
        "inviter": inviter.get("username"),
        "inviter_name": inviter.get("global_name"),
    }


def enabled() -> bool:
    return get_config()["scan"].get("discord_invites", True)
