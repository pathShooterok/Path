import base64
from urllib.parse import urlparse, parse_qs
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from html import unescape
import re


TAG_RE = re.compile(r"<[^>]+>")


def clean_html(text: str) -> str:
    text = TAG_RE.sub("", text)
    return unescape(text).strip()


def search_bing(target: str, limit: int = 10) -> list[dict]:
    query = quote_plus(f'"{target}"')
    search_url = f"https://www.bing.com/search?q={query}"

    request = Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            )
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            html = response.read().decode(
                "utf-8",
                errors="ignore",
            )
    except Exception as error:
        print(f"[-] Bing request failed: {error}")
        return []

    print(f"[*] Bing HTML received: {len(html)} chars")

    blocks = re.findall(
        r'<li[^>]*class="[^"]*\bb_algo\b[^"]*"[^>]*>.*?</li>',
        html,
        re.IGNORECASE | re.DOTALL,
    )

    results = []

    for block in blocks:
        match = re.search(
            r'<h2[^>]*>\s*'
            r'<a[^>]+href="([^"]+)"[^>]*>'
            r'(.*?)'
            r'</a>',
            block,
            re.IGNORECASE | re.DOTALL,
        )

        if not match:
            continue

        url = unescape(match.group(1))
        url = decode_bing_url(url)
        title = clean_html(match.group(2))
        

        if not url.startswith(("http://", "https://")):
            continue

        if not title:
            continue

        target_lower = target.lower()

        if target_lower not in title.lower() and target_lower not in url.lower():
            continue

        results.append(
            {
                "title": title,
                "url": url,
                
            }
            
        )

        if len(results) >= limit:
            break

    return results
def decode_bing_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        encoded = params.get("u", [None])[0]

        if not encoded:
            return url

        if encoded.startswith("a1"):
            encoded = encoded[2:]

        padding = "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(
            encoded + padding
        ).decode("utf-8", errors="ignore")

        if decoded.startswith(("http://", "https://")):
            return decoded

    except Exception:
        pass

    return url