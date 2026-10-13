MARKERS = (
    "detected unusual traffic",
    "unusual traffic from your computer",
    "our systems have detected",
    "/sorry/index",
    "enablejs",
    "captcha",
    "solve the challenge",
    "one last step",
    "verify you are a human",
    "anomaly-modal",
    "если у вас возникли проблемы с доступом к google поиску",
)

SCAN_LIMIT = 200_000


def is_block_page(text: str) -> bool:
    lowered = text[:SCAN_LIMIT].lower()
    return any(marker in lowered for marker in MARKERS)


BLOCK_HINT = "Wait a few minutes, switch network, or use another source (--sources)."
