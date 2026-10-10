import re
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from core.http import fetch, decode_body

TAG_RE = re.compile(r"<[^>]+>")
RESULT_RE = re.compile(
    r'<a[^>]+class="[^"]*\bresult__a\b[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
SNIPPET_RE = re.compile(
    r'<a[^>]+class="[^"]*\bresult__snippet\b[^"]*"[^>]*>(.*?)</a>', re.I | re.S
)


def _clean(text: str) -> str:
    return unescape(TAG_RE.sub("", text)).strip()


def _real_url(href: str) -> str:
    href = unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            return unquote(target)
    return href


def search_duckduckgo(query: str, limit: int = 10, **_) -> list[dict]:
    response = fetch(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}")
    if not response["ok"]:
        print(f"[-] DuckDuckGo request failed: {response['error']}")
        return []

    html = decode_body(response)
    if "anomaly" in html.lower() and "result__a" not in html:
        print("[-] DuckDuckGo returned a bot-check page.")
        return []

    if "result__a" not in html:
        no_results = "no results" in html.lower() or "нет результатов" in html.lower()
        print("[*] DuckDuckGo: no results for this query." if no_results
              else f"[-] DuckDuckGo: unexpected page ({len(html)} chars), likely blocked.")
        return []

    snippets = [_clean(s) for s in SNIPPET_RE.findall(html)]
    results = []
    for i, (href, title) in enumerate(RESULT_RE.findall(html)):
        url = _real_url(href)
        title = _clean(title)
        if not url.startswith(("http://", "https://")) or not title:
            continue
        results.append({
            "title": title, "url": url,
            "snippet": snippets[i] if i < len(snippets) else "",
            "source": "duckduckgo",
        })
        if len(results) >= limit:
            break
    return results
