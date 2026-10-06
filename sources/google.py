import re
from html import unescape
from urllib.parse import parse_qs, quote_plus, urlparse

from core.http import fetch, decode_body

TAG_RE = re.compile(r"<[^>]+>")
RESULT_RE = re.compile(
    r'<a[^>]+href="(/url\?[^"]+|https?://[^"]+)"[^>]*>\s*<h3[^>]*>(.*?)</h3>', re.I | re.S
)
BLOCK_MARKERS = (
    "detected unusual traffic",
    "Если у вас возникли проблемы с доступом к Google Поиску",
    "enablejs",
    "/sorry/index",
)


def search_google(query: str, limit: int = 10, **_) -> list[dict]:
    response = fetch(f"https://www.google.com/search?q={quote_plus(query)}&num={limit}&hl=en")
    if not response["ok"]:
        print(f"[-] Google request failed: {response['error']}")
        return []

    html = decode_body(response)
    results = []
    for href, title in RESULT_RE.findall(html):
        href = unescape(href)
        if href.startswith("/url?"):
            href = parse_qs(urlparse(href).query).get("q", [""])[0]
        title = unescape(TAG_RE.sub("", title)).strip()
        if href.startswith(("http://", "https://")) and title and "google." not in urlparse(href).netloc:
            results.append({"title": title, "url": href, "snippet": "", "source": "google"})
        if len(results) >= limit:
            break

    if not results and any(marker in html for marker in BLOCK_MARKERS):
        print("[-] Google returned a bot-check / JS-only page.")
    return results
