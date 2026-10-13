import re
from html import escape

CSS = """
:root{--bg:#fff;--fg:#1c1f24;--muted:#667085;--card:#f6f7f9;--line:#e3e6ea;--high:#157f3b;--medium:#b7791f;--low:#8a8f98;--accent:#2b59c3}
@media(prefers-color-scheme:dark){:root{--bg:#14161a;--fg:#e6e8eb;--muted:#9aa3ad;--card:#1d2026;--line:#2c3038;--high:#4cc277;--medium:#e0b050;--low:#8a8f98;--accent:#7aa2f7}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:920px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:32px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
.meta{color:var(--muted);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:8px 0}
.head{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.badge{font-size:11px;font-weight:600;text-transform:uppercase;padding:1px 7px;border-radius:10px;border:1px solid currentColor}
.high{color:var(--high)}.medium{color:var(--medium)}.low{color:var(--low)}
.value{font-weight:600;word-break:break-word}
.row{font-size:13px;color:var(--muted);word-break:break-word}
a{color:var(--accent)}
.empty{color:var(--muted)}
"""

_SAFE_URL = re.compile(r"^https?://", re.I)


def _link(url: str) -> str:
    text = escape(url)
    if _SAFE_URL.match(url or ""):
        return f'<a href="{escape(url, quote=True)}" rel="noopener noreferrer nofollow">{text}</a>'
    return text


def _value(finding) -> str:
    raw = finding.value
    if ": " in raw and finding.kind in ("social", "linked_social"):
        label, url = raw.split(": ", 1)
        return f"{escape(label)}: {_link(url)}"
    if finding.kind in ("link",) and _SAFE_URL.match(raw):
        return _link(raw)
    return escape(raw)


def _sources(source: str) -> str:
    return " | ".join(_link(part.strip()) for part in (source or "").split(" | ") if part.strip())


def _card(finding, title=None) -> str:
    level = finding.confidence if finding.confidence in ("high", "medium", "low") else "low"
    rows = []
    if finding.source:
        rows.append(f'<div class="row">Source: {_sources(finding.source)}</div>')
    if finding.source_type and finding.source_type != "unknown":
        rows.append(f'<div class="row">Type: {escape(finding.source_type)}</div>')
    if finding.provider:
        rows.append(f'<div class="row">Provider: {escape(finding.provider)}</div>')
    if finding.evidence:
        rows.append(f'<div class="row">Evidence: {escape(finding.evidence)}</div>')
    heading = f"{escape(title)} " if title else ""
    return (
        f'<div class="card"><div class="head"><span class="badge {level}">{escape(finding.confidence)}</span>'
        f'<span class="value">{heading}{_value(finding)}</span></div>{"".join(rows)}</div>'
    )


def _section(title: str, cards: list[str]) -> str:
    if not cards:
        return ""
    return f"<h2>{escape(title)}</h2>" + "".join(cards)


def render_html(report) -> str:
    correlation, social, emails, other = [], [], [], []
    rank = {"high": 0, "medium": 1, "low": 2}

    for f in report.findings:
        if f.kind in ("correlation", "correlation_unmatched"):
            correlation.append(f)
        elif f.kind in ("social", "linked_social"):
            social.append(f)
        elif f.kind == "email":
            emails.append(f)
        else:
            other.append(f)

    social.sort(key=lambda f: rank.get(f.confidence, 3))
    emails.sort(key=lambda f: (f.classification != "personal_candidate", rank.get(f.confidence, 3)))

    body = [
        _section("Correlation", [
            _card(f, "Same person?" if f.kind == "correlation" else "Unconfirmed")
            for f in correlation
        ]),
        _section("Social profiles", [_card(f) for f in social]),
        _section("Emails", [_card(f) for f in emails]),
        _section("Other findings", [_card(f, f.kind.upper()) for f in other]),
    ]
    content = "".join(body) or '<p class="empty">No public findings.</p>'

    from core import __version__
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Path report: {escape(report.target)}</title><style>{CSS}</style></head><body><main>"
        f"<h1>{escape(report.target)}</h1>"
        f'<div class="meta">Path v{escape(__version__)} · {escape(report.started_at)} · '
        f"{len(report.findings)} findings</div>{content}</main></body></html>"
    )


def save_html(report, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(report))
