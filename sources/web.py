from core.http import fetch, decode_body


def fetch_url(url: str) -> dict:
    response = fetch(url)

    if not response["ok"]:
        return {
            "url": url, "final_url": response["final_url"], "status": response["status"],
            "content_type": "", "text": "", "error": response["error"],
        }

    content_type = response["headers"].get("Content-Type", "") if response["headers"] else ""

    if response["truncated"]:
        return {
            "url": url, "final_url": response["final_url"], "status": response["status"],
            "content_type": content_type, "text": "",
            "error": "Response is larger than the configured limit",
        }

    return {
        "url": url, "final_url": response["final_url"], "status": response["status"],
        "content_type": content_type, "text": decode_body(response), "error": None,
    }
