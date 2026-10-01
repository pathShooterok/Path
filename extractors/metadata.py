from html.parser import HTMLParser


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()

        self.title = ""
        self.description = ""
        self.og_title = ""
        self.og_description = ""
        self.og_url = ""

        self._inside_title = False
        self._title_parts = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "title":
            self._inside_title = True
            self._title_parts = []

        if tag != "meta":
            return

        name = attrs_dict.get("name", "").lower()
        property_name = attrs_dict.get("property", "").lower()
        content = attrs_dict.get("content", "").strip()

        if not content:
            return

        if name == "description":
            self.description = content

        elif property_name == "og:title":
            self.og_title = content

        elif property_name == "og:description":
            self.og_description = content

        elif property_name == "og:url":
            self.og_url = content

    def handle_data(self, data):
        if self._inside_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag):
        if tag != "title":
            return

        self.title = " ".join(
            part.strip()
            for part in self._title_parts
            if part.strip()
        )

        self._inside_title = False


def extract_metadata(html: str) -> dict:
    parser = MetadataParser()

    try:
        parser.feed(html)
    except Exception:
        pass

    return {
        "title": parser.title,
        "description": parser.description,
        "og_title": parser.og_title,
        "og_description": parser.og_description,
        "og_url": parser.og_url,
    }