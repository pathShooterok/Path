from urllib.parse import quote_plus
from urllib.request import Request, urlopen


def search_google(target: str, limit: int = 10) -> list[dict]:
    query = quote_plus(f'"{target}"')
    search_url = f"https://www.google.com/search?q={query}"

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
        print(f"[-] Google request failed: {error}")
        return []

    # Google вернул страницу с сообщением об ошибке/ограничении.
    if "Если у вас возникли проблемы с доступом к Google Поиску" in html:
        print("[-] Google returned an access/problem page.")
        return []

    if "Our systems have detected unusual traffic" in html:
        print("[-] Google returned an unusual-traffic page.")
        return []

    if "detected unusual traffic" in html.lower():
        print("[-] Google returned an unusual-traffic page.")
        return []

    print(f"[*] Google HTML received: {len(html)} chars")

    # Пока только диагностика.
    # Парсер результатов добавим после определения
    # фактической структуры страницы результатов.

    return []