import base64
import re
from html import unescape
from urllib.parse import parse_qs, quote_plus, urlparse

from core.blocks import BLOCK_HINT, is_block_page
from core.http import fetch, decode_body

TAG_RE = re.compile(r"<[^>]+>")
BLOCK_RE = re.compile(r'<li[^>]*class="[^"]*\bb_algo\b[^"]*"[^>]*>.*?</li>', re.I | re.S)
LINK_RE = re.compile(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
SNIPPET_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.I | re.S)


FALLBACK_RE = re.compile(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>(?=(.{0,2500}))', re.I | re.S)
NO_RESULTS_RE = re.compile(r'<li[^>]*class="[^"]*\bb_no\b', re.I)
OWN_HOSTS = ("bing.com", "microsoft.com", "live.com", "msn.com", "office.com", "windows.com")


def _is_own(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in OWN_HOSTS)


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
                require_target_match: bool = False, _retry: bool = True) -> list[dict]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}&count={max(limit, 10)}&setlang=en&mkt=en-US&cc=US"
    response = fetch(url)
    if not response["ok"]:
        print(f"[-] Bing request failed: {response['error']}")
        return []

    html = decode_body(response)
    if NO_RESULTS_RE.search(html):
        plain = query.replace('"', "").strip()
        if _retry and plain and plain != query:
            print("[*] Bing: no results for the quoted query, retrying without quotes")
            return search_bing(plain, limit, target, require_target_match, _retry=False)
        print("[-] Bing says there are no results for this query "
              "(it may also be a soft block for automated requests)")
        return []
    items = [(LINK_RE.search(block), block) for block in BLOCK_RE.findall(html)]
    items = [(m, block) for m, block in items if m]
    fallback = False
    if not items:
        if is_block_page(html):
            print(f"[-] Bing returned a captcha / bot-check page. {BLOCK_HINT}")
            return []
        items = [(m, m.group(3)) for m in FALLBACK_RE.finditer(html)]
        fallback = True
        if not items:
            print(f"[-] Bing: no results parsed ({len(html)} chars, layout may have changed)")
            return []

    results = []
    for m, block in items:
        href = decode_bing_url(unescape(m.group(1)))
        title = clean_html(m.group(2))
        if not href.startswith(("http://", "https://")) or not title:
            continue
        if fallback and _is_own(href):
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

    if fallback:
        if results:
            print("[*] Bing: standard result blocks not found, used fallback parser")
        else:
            print(f"[-] Bing: no results parsed ({len(html)} chars, layout may have changed)")
    return results
