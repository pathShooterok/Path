from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from html import unescape
import re


RESULT_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

TAG_RE = re.compile(r"<[^>]+>")


def search_duckduckgo(target: str, limit: int = 10) -> list[dict]:
    query = quote_plus(f'"{target}"')
    search_url = f"https://html.duckduckgo.com/html/?q={query}"

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
        print(f"[-] DuckDuckGo request failed: {error}")
        return []

    results = []

    for href, title in RESULT_RE.findall(html):
        href = unescape(href)

        if not href.startswith(("http://", "https://")):
            continue

        title = TAG_RE.sub("", title)
        title = unescape(title).strip()

        if not title:
            continue

        results.append(
            {
                "title": title,
                "url": href,
            }
        )

        if len(results) >= limit:
            break

    return results