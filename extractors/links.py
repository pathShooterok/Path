from html.parser import HTMLParser
from urllib.parse import urljoin


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        for name, value in attrs:
            if name == "href" and value:
                self.links.append(value)
                break


def extract_links(html: str, base_url: str) -> list[str]:
    parser = LinkParser()

    try:
        parser.feed(html)
    except Exception:
        return []

    results = set()

    for link in parser.links:
        absolute_url = urljoin(base_url, link)

        if absolute_url.startswith(("http://", "https://")):
            results.add(absolute_url)

    return sorted(results)