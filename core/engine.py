from core.models import Finding, new_report

from sources.web import search_public_web, fetch_url
from sources.bing import search_bing

from extractors.email import extract_emails
from extractors.links import extract_links
from extractors.metadata import extract_metadata
from extractors.mail_provider import identify_provider
from extractors.email_classification import classify_email
from extractors.link_filter import is_interesting_link
from extractors.public_identity import (
    extract_visible_text,
    extract_text_blocks,
    extract_usernames,
    extract_name_candidates,
    extract_social_links,
    extract_structured_names,
)


def _add_finding(report, finding):
    for existing in report.findings:
        if finding.kind == "email" and existing.kind == "email":
            if existing.value.lower() == finding.value.lower():
                return

        if (
            existing.kind == finding.kind
            and existing.value == finding.value
            and existing.source == finding.source
        ):
            return

    report.findings.append(finding)


def _add_metadata_findings(
    report,
    metadata,
    source,
    source_type,
    confidence,
    linked=False,
):
    for key, value in metadata.items():
        if not value:
            continue

        kind = f"linked_{key}" if linked else key

        evidence = (
            "Metadata extracted from a linked public page"
            if linked
            else "Page metadata extracted directly from scanned public URL"
        )

        _add_finding(
            report,
            Finding(
                kind=kind,
                value=value,
                source=source,
                evidence=evidence,
                confidence=confidence,
                source_type=source_type,
            ),
        )


def _add_email_findings(
    report,
    emails,
    source,
    source_type,
    confidence,
    linked=False,
):
    for email in emails:
        provider = identify_provider(email)
        classification = classify_email(email)

        evidence = (
            "Email found on a linked public page"
            if linked
            else "Email found directly on scanned public URL"
        )

        _add_finding(
            report,
            Finding(
                kind="email",
                value=email,
                source=source,
                evidence=evidence,
                confidence=confidence,
                source_type=source_type,
                provider=provider,
                classification=classification,
            ),
        )


def _add_identity_findings(
    report,
    html,
    links,
    source,
    source_type,
    confidence,
    linked=False,
):
    text = extract_visible_text(html)

    if not text:
        return

    text_blocks = extract_text_blocks(html)

    for block in text_blocks:
        if not any(
            marker in block
            for marker in ("@", "http://", "https://")
        ):
            continue

        kind = "linked_text" if linked else "text"

        _add_finding(
            report,
            Finding(
                kind=kind,
                value=block,
                source=source,
                evidence="Identity-relevant text extracted from the visible page content",
                confidence=confidence,
                source_type=source_type,
            ),
        )

    usernames = extract_usernames(text)

    for username in usernames:
        kind = "linked_username" if linked else "username"

        _add_finding(
            report,
            Finding(
                kind=kind,
                value=username,
                source=source,
                evidence="Public username mention extracted from visible page content",
                confidence="low",
                source_type=source_type,
            ),
        )

    name_candidates = extract_name_candidates(text)

    for name in name_candidates:
        kind = "linked_name_candidate" if linked else "name_candidate"

        _add_finding(
            report,
            Finding(
                kind=kind,
                value=name,
                source=source,
                evidence="Possible person-name pattern found in public page content",
                confidence="low",
                source_type=source_type,
            ),
        )

    structured_names = extract_structured_names(html)

    for name in structured_names:
        kind = "linked_name" if linked else "name"

        _add_finding(
            report,
            Finding(
                kind=kind,
                value=name,
                source=source,
                evidence="Person name extracted from public structured metadata",
                confidence="high",
                source_type=source_type,
            ),
        )

    social_links = extract_social_links(links)

    for social in social_links:
        kind = "linked_social" if linked else "social"

        _add_finding(
            report,
            Finding(
                kind=kind,
                value=f"{social['platform']}: {social['url']}",
                source=source,
                evidence="Public social-media profile link extracted from page",
                confidence="high",
                source_type=source_type,
            ),
        )


def run_trace(target: str):
    report = new_report(target)

    print(f"[*] Searching public web for: {target}")

    pages = search_public_web(target)

    for page in pages:
        text = page.get("text", "")
        source = page.get("url", "")

        if not text:
            continue

        emails = extract_emails(text)

        _add_email_findings(
            report,
            emails,
            source,
            "search_engine",
            "high",
        )

    print("[*] Searching Bing...")

    bing_results = search_bing(target)

    for result in bing_results:
        _add_finding(
            report,
            Finding(
                kind="web_result",
                value=result["title"],
                source=result["url"],
                evidence=f"Search result returned for identifier: {target}",
                confidence="medium",
                source_type="search_engine",
            ),
        )

    return report


def scan_linked_pages(links: list[str], max_links: int = 10):
    results = []
    seen = set()

    for link in links:
        if link in seen:
            continue

        seen.add(link)

        if not is_interesting_link(link):
            continue

        if len(results) >= max_links:
            break

        print(f"[*] Scanning linked page: {link}")

        page = fetch_url(link)

        if page.get("error"):
            print(f"[-] Failed to fetch linked page: {page['error']}")
            continue

        final_url = page.get("final_url", link)
        content_type = page.get("content_type", "")
        html = page.get("text", "")

        if "text/html" not in content_type.lower():
            continue

        if not html:
            continue

        results.append(
            {
                "url": final_url,
                "html": html,
            }
        )

    return results


def run_url_scan(url: str):
    report = new_report(url)

    print(f"[*] Fetching URL: {url}")

    page = fetch_url(url)

    if page.get("error"):
        _add_finding(
            report,
            Finding(
                kind="error",
                value=page["error"],
                source=url,
                evidence="URL fetch failed",
                confidence="high",
                source_type="direct_page",
            ),
        )
        return report

    final_url = page.get("final_url", url)
    status = page.get("status")
    content_type = page.get("content_type", "")
    html = page.get("text", "")

    print(f"[*] HTTP status: {status}")
    print(f"[*] Final URL: {final_url}")

    if "text/html" not in content_type.lower():
        _add_finding(
            report,
            Finding(
                kind="page_type",
                value=content_type or "unknown",
                source=final_url,
                evidence="URL did not return an HTML page",
                confidence="high",
                source_type="direct_page",
            ),
        )
        return report

    if not html:
        return report

    metadata = extract_metadata(html)

    _add_metadata_findings(
        report,
        metadata,
        final_url,
        "direct_page",
        "high",
    )

    emails = extract_emails(html)

    _add_email_findings(
        report,
        emails,
        final_url,
        "direct_page",
        "high",
    )

    links = extract_links(html, final_url)

    for link in links:
        _add_finding(
            report,
            Finding(
                kind="link",
                value=link,
                source=final_url,
                evidence="Link extracted directly from scanned public URL",
                confidence="medium",
                source_type="direct_page",
            ),
        )

    _add_identity_findings(
        report,
        html,
        links,
        final_url,
        "direct_page",
        "medium",
    )

    linked_pages = scan_linked_pages(
        links,
        max_links=10,
    )

    for linked_page in linked_pages:
        linked_url = linked_page["url"]
        linked_html = linked_page["html"]

        linked_metadata = extract_metadata(linked_html)

        _add_metadata_findings(
            report,
            linked_metadata,
            linked_url,
            "linked_page",
            "medium",
            linked=True,
        )

        linked_emails = extract_emails(linked_html)

        _add_email_findings(
            report,
            linked_emails,
            linked_url,
            "linked_page",
            "medium",
            linked=True,
        )

        linked_links = extract_links(
            linked_html,
            linked_url,
        )

        _add_identity_findings(
            report,
            linked_html,
            linked_links,
            linked_url,
            "linked_page",
            "medium",
            linked=True,
        )

    return report