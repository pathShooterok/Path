from urllib.parse import urlparse, urlunparse

from core.models import Finding, new_report

from core.config import get_config
from core.correlate import correlate_profiles
from sources import run_search
from sources.web import fetch_url
from sources.profiles import probe_profiles, github_api

from extractors.email import extract_emails
from extractors.links import extract_links
from extractors.metadata import extract_metadata
from extractors.mail_provider import identify_provider
from extractors.email_classification import classify_email
from extractors.link_filter import is_interesting_link
from extractors.social import (
    extract_social_profiles,
    parse_social_url,
    find_social_in_text,
    match_level,
    _norm,
    match_at_least,
    confidence_for,
)
from extractors.public_identity import (
    extract_visible_text,
    extract_text_blocks,
    extract_usernames,
    extract_name_candidates,
    extract_social_links,
    extract_structured_names,
)


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication: lowercase scheme/host, remove default ports,
    remove fragment. Preserve path and query exactly as-is."""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        # Remove default ports (handle IPv6: [::1]:80 -> [::1])
        if netloc.startswith("["):
            # IPv6: [host]:port
            if scheme == "http" and netloc.endswith("]:80"):
                netloc = netloc[:-4] + "]"
            elif scheme == "https" and netloc.endswith("]:443"):
                netloc = netloc[:-5] + "]"
        else:
            # IPv4 or hostname
            if (scheme == "http" and netloc.endswith(":80")) or (scheme == "https" and netloc.endswith(":443")):
                netloc = netloc.rsplit(":", 1)[0]
        # Preserve path exactly (including trailing slash)
        path = parsed.path
        # Preserve query exactly (no sorting)
        query = parsed.query
        # Reconstruct without fragment
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, ""))
        return normalized
    except Exception:
        return url


def _add_finding(report, finding):
    for existing in report.findings:
        if finding.kind == "email" and existing.kind == "email":
            if existing.value.lower() == finding.value.lower():
                return

        # Normalize source URLs for link/web_result deduplication
        existing_source_norm = _normalize_url(existing.source) if existing.source else existing.source
        finding_source_norm = _normalize_url(finding.source) if finding.source else finding.source

        if (
            existing.kind == finding.kind
            and existing.value == finding.value
            and existing_source_norm == finding_source_norm
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
    redundant = {
        "og_title": metadata.get("title"),
        "og_description": metadata.get("description"),
        "og_url": source,
    }

    for key, value in metadata.items():
        if not value:
            continue

        # og:* tags that just repeat the plain tag / the page URL add only noise
        if key in redundant and redundant[key] and (
            value.strip() == redundant[key].strip()
            or (key == "og_url" and _normalize_url(value) == _normalize_url(source))
        ):
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

    _add_social_findings(report, links, source, source_type, linked=linked, outbound_only=True)


MAX_SOCIAL_PER_PAGE = 20


def _add_social_findings(report, links, source, source_type, linked=False, target=None,
                         outbound_only=False):
    profiles = extract_social_profiles(links)

    # On a profile page, links to the same platform are site navigation and
    # sidebar users, not the person's other accounts: keep only outbound ones.
    own = parse_social_url(source) if outbound_only else None
    if own:
        profiles = [p for p in profiles if p["platform"] != own["platform"]]
    profiles = profiles[:MAX_SOCIAL_PER_PAGE]
    kind = "linked_social" if linked else "social"

    for profile in profiles:
        level = match_level(profile["username"], target) if target else "none"
        evidence = "Public social-media profile link extracted from page"
        confidence = "high"
        if target:
            evidence = f"Profile username '{profile['username']}' vs target: {level}"
            confidence = confidence_for(level) if level != "none" else "low"

        _add_finding(
            report,
            Finding(
                kind=kind,
                value=f"{profile['platform']}: {profile['url']}",
                source=source,
                evidence=evidence,
                confidence=confidence,
                source_type=source_type,
            ),
        )

    return profiles


def _analyze_page(report, html, url, source_type, confidence, linked):
    """Metadata, emails, links and identity for one fetched HTML page."""
    _add_metadata_findings(report, extract_metadata(html), url, source_type, confidence, linked=linked)
    _add_email_findings(report, extract_emails(html), url, source_type, confidence, linked=linked)
    page_links = extract_links(html, url)
    _add_identity_findings(report, html, page_links, url, source_type, confidence, linked=linked)
    return page_links


def run_trace(target: str, only_sources: list[str] | None = None):
    cfg = get_config()
    trace_cfg = cfg["trace"]
    report = new_report(target)

    print(f"[*] Tracing: {target}")

    queries = [q.replace("{target}", target) for q in trace_cfg["queries"]]
    results = run_search(target, queries, only=only_sources)

    profiles = []  # (match_level, profile)

    if cfg["profiles"]["enabled"]:
        _probe_known_platforms(report, target)

    norm_target = _norm(target)
    dropped = 0

    for result in results:
        url, title, snippet = result["url"], result["title"], result.get("snippet", "")

        if trace_cfg["require_target_in_result"] and len(norm_target) >= 3:
            if norm_target not in _norm(f"{url} {title} {snippet}"):
                dropped += 1
                continue

        _add_finding(
            report,
            Finding(
                kind="web_result",
                value=title,
                source=url,
                evidence=f"Search result ({result['source']}) for: {target}",
                confidence="medium",
                source_type="search_engine",
            ),
        )

        # emails visible in the search snippet itself
        _add_email_findings(
            report, extract_emails(f"{title} {snippet}"),
            url, "search_engine", "medium",
        )

        # social profiles: the result URL itself and links mentioned in the snippet
        candidates = [url] + [p["found_as"] for p in find_social_in_text(snippet)]
        for profile in _add_social_findings(
            report, candidates, url, "search_engine", target=target
        ):
            level = match_level(profile["username"], target)
            profiles.append((level, profile))

    if dropped:
        print(f"[*] Dropped {dropped} search results that do not mention the target")

    if trace_cfg["scan_social_profiles"]:
        _scan_profiles(report, target, profiles, trace_cfg)

    correlate_profiles(report, target)

    return report


def _probe_known_platforms(report, target):
    print(f"[*] Probing known platforms for username: {target}")
    found = probe_profiles(target)

    for profile in found:
        variant = profile.get("variant")
        _add_finding(
            report,
            Finding(
                kind="social",
                value=f"{profile['platform']}: {profile['url']}",
                source=profile["url"],
                evidence=(
                    f"Profile '{profile['username']}' exists; spelling variant of '{target}', "
                    "may be a different person"
                    if variant else
                    f"Profile page exists for username '{target}' "
                    "(existence only: not verified to be the same person)"
                ),
                confidence="low" if variant else "medium",
                source_type="profile_probe",
            ),
        )
        if profile.get("name"):
            _add_finding(
                report,
                Finding(kind="name", value=profile["name"], source=profile["url"],
                        evidence=f"Display name from {profile['platform']} public profile",
                        confidence="low" if variant else "medium",
                        source_type="profile_probe"),
            )
        if profile.get("html"):
            _analyze_page(report, profile["html"], profile["url"], "profile_probe",
                          "low" if variant else "medium", linked=True)

        if profile["platform"] == "GitHub" and get_config()["profiles"]["github_api"]:
            _add_github_api_findings(report, profile["username"], profile["url"])


def _add_github_api_findings(report, username, url):
    data = github_api(username)
    if not data:
        return

    def add(kind, value, evidence, confidence="high"):
        if value:
            _add_finding(report, Finding(kind=kind, value=value, source=url,
                                         evidence=evidence, confidence=confidence,
                                         source_type="github_api"))

    add("name", data.get("name"), "Name from public GitHub profile")
    add("text", data.get("bio"), "Bio from public GitHub profile", "medium")
    add("text", data.get("location"), "Location from public GitHub profile", "medium")
    add("text", data.get("company"), "Company from public GitHub profile", "medium")
    if data.get("twitter_username"):
        _add_social_findings(report, [f"https://x.com/{data['twitter_username']}"],
                             url, "github_api", linked=True)
    if data.get("blog"):
        blog = data["blog"] if data["blog"].startswith("http") else "https://" + data["blog"]
        add("link", blog, "Website from public GitHub profile", "high")
    # only an address the user chose to publish on their profile
    if data.get("email"):
        _add_email_findings(report, [data["email"]], url, "github_api", "high")
    if data.get("bio"):
        _add_email_findings(report, extract_emails(data["bio"]), url, "github_api", "high")


def _scan_profiles(report, target, profiles, trace_cfg):
    """Fetch the best-matching public profile pages and extract bio/email/links."""
    minimum = trace_cfg["min_profile_match"]
    rank = {"exact": 0, "normalized": 1, "partial": 2}
    chosen, seen = [], set()

    for level, profile in sorted(profiles, key=lambda x: rank.get(x[0], 9)):
        if not match_at_least(level, minimum) or profile["url"] in seen:
            continue
        seen.add(profile["url"])
        chosen.append(profile)
        if len(chosen) >= trace_cfg["max_profiles"]:
            break

    for profile in chosen:
        print(f"[*] Reading profile: {profile['platform']} / {profile['username']}")
        page = fetch_url(profile["url"])
        if page.get("error") or not page.get("text"):
            print(f"[-] Profile not readable: {page.get('error') or 'empty'}")
            continue
        if "text/html" not in page.get("content_type", "").lower():
            continue

        final_url = page.get("final_url", profile["url"])
        _analyze_page(report, page["text"], final_url, "social_profile", "medium", linked=True)


def scan_linked_pages(links: list[str], max_links: int | None = None, seen: set | None = None,
                      always: set | None = None):
    results = []
    if max_links is None:
        max_links = get_config()["scan"]["max_linked_pages"]
    if seen is None:
        seen = set()

    for link in links:
        norm_link = _normalize_url(link)
        if norm_link in seen:
            continue

        seen.add(norm_link)

        if not (always and link in always) and not is_interesting_link(link):
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

    # Pre-populate seen with the main URL to avoid re-scanning it
    seen = {_normalize_url(final_url)}

    always = set()
    if get_config()["scan"]["follow_social_links"]:
        # social profile links bypass the keyword filter (they never contain /about etc.)
        always = {p["found_as"] for p in extract_social_profiles(links)}

    linked_pages = scan_linked_pages(links, seen=seen, always=always)

    for linked_page in linked_pages:
        _analyze_page(
            report, linked_page["html"], linked_page["url"],
            "linked_page", "medium", linked=True,
        )

    return report
