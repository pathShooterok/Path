from urllib.parse import quote_plus
from urllib.request import Request, urlopen


MAX_RESPONSE_SIZE = 2 * 1024 * 1024


def search_public_web(target: str):
    query = quote_plus(f'"{target}"')
    url = f"https://www.google.com/search?q={query}"

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
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

        return [
            {
                "url": url,
                "text": html,
            }
        ]

    except Exception as error:
        return [
            {
                "url": url,
                "text": "",
                "error": str(error),
            }
        ]


def fetch_url(url: str) -> dict:
    if not url.startswith(("http://", "https://")):
        return {
            "url": url,
            "final_url": url,
            "status": None,
            "content_type": "",
            "text": "",
            "error": "Only http:// and https:// URLs are supported",
        }

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/136.0.0.0 Safari/537.36"
            )
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            content_type = response.headers.get(
                "Content-Type",
                "",
            )

            data = response.read(MAX_RESPONSE_SIZE + 1)

            if len(data) > MAX_RESPONSE_SIZE:
                return {
                    "url": url,
                    "final_url": response.geturl(),
                    "status": response.status,
                    "content_type": content_type,
                    "text": "",
                    "error": "Response is larger than 2 MB",
                }

            html = data.decode(
                "utf-8",
                errors="ignore",
            )

            return {
                "url": url,
                "final_url": response.geturl(),
                "status": response.status,
                "content_type": content_type,
                "text": html,
                "error": None,
            }

    except Exception as error:
        return {
            "url": url,
            "final_url": url,
            "status": None,
            "content_type": "",
            "text": "",
            "error": str(error),
        }