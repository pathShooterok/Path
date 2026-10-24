from extractors.social import parse_social_url


def summarize(report) -> dict:
    profiles, names, sites = set(), set(), set()
    emails, breaches, groups = set(), 0, 0
    for finding in report.findings:
        kind = finding.kind
        if kind in ("social", "linked_social"):
            parsed = parse_social_url(finding.value.split(": ", 1)[-1])
            if parsed:
                profiles.add((parsed["platform"], parsed["username"].lower()))
        elif kind in ("name", "linked_name"):
            names.add(finding.value.strip().lower())
        elif kind == "email":
            emails.add(finding.value.lower())
        elif kind == "link" and finding.evidence.startswith("Website"):
            sites.add(finding.value.lower().rstrip("/"))
        elif kind == "breach":
            breaches += 1
        elif kind == "correlation":
            groups += 1
    return {
        "profiles": len(profiles), "emails": len(emails), "names": len(names),
        "websites": len(sites), "breaches": breaches, "same_person_groups": groups,
    }


LABELS = (
    ("profiles", "profile"), ("emails", "email"), ("names", "name"), ("websites", "website"),
    ("breaches", "breach record"), ("same_person_groups", "likely same-person group"),
)


def format_summary(counts: dict) -> str:
    parts = []
    for key, label in LABELS:
        count = counts.get(key, 0)
        if count:
            parts.append(f"{count} {label}{'' if count == 1 else 's'}")
    return ", ".join(parts)
