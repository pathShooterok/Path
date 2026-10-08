import base64
import re
from html import unescape
from urllib.parse import parse_qs, quote_plus, urlparse

from core.http import fetch, decode_body

TAG_RE = re.compile(r"<[^>]+>")
BLOCK_RE = re.compile(r'<li[^>]*class="[^"]*\bb_algo\b[^"]*"[^>]*>.*?</li>', re.I | re.S)
LINK_RE = re.compile(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
SNIPPET_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.I | re.S)


def clean_html(text: str) -> str:
    return unescape(TAG_RE.sub("", text)).strip()


def decode_bing_url(url: str) -> str:
    try:
        encoded = parse_qs(urlparse(url).query).get("u", [None])[0]
        if not encoded:
            return url
        if encoded.startswith("a1"):
            encoded = encoded[2:]
        decoded = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        ).decode("utf-8", errors="ignore")
        if decoded.startswith(("http://", "https://")):
            return decoded
    except Exception:
        pass
    return url


def search_bing(query: str, limit: int = 10, target: str | None = None,
                require_target_match: bool = False) -> list[dict]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}&count={max(limit, 10)}&setlang=en&mkt=en-US&cc=US"
    response = fetch(url)
    if not response["ok"]:
        print(f"[-] Bing request failed: {response['error']}")
        return []

    html = decode_body(response)
    blocks = BLOCK_RE.findall(html)
    if not blocks:
        print(f"[-] Bing: no results parsed ({len(html)} chars; captcha or layout change?)")
        return []

    results = []
    for block in blocks:
        m = LINK_RE.search(block)
        if not m:
            continue
        href = decode_bing_url(unescape(m.group(1)))
        title = clean_html(m.group(2))
        if not href.startswith(("http://", "https://")) or not title:
            continue

        if require_target_match and target:
            t = target.lower()
            if t not in title.lower() and t not in href.lower():
                continue

        snippet = ""
        sm = SNIPPET_RE.search(block)
        if sm:
            snippet = clean_html(sm.group(1))

        results.append({"title": title, "url": href, "snippet": snippet, "source": "bing"})
        if len(results) >= limit:
            break
    return results
