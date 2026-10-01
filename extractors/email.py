import re


EMAIL_RE = re.compile(
    r"(?i)\b"
    r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@"
    r"[a-z0-9-]+"
    r"(?:\.[a-z0-9-]+)+"
    r"\b"
)


def extract_emails(text: str) -> list[str]:
    return sorted(set(EMAIL_RE.findall(text)))