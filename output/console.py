BANNER = r"""
[91m .S_sSSs           .S_SSSs          sdSS_SSSSSSbs         .S    S.   
.SS~YS%%b         .SS~SSSSS         YSSS~S%SSSSSP        .SS    SS.  
S%S   `S%b        S%S   SSSS             S%S             S%S    S%S  
S%S    S%S        S%S    S%S             S%S             S%S    S%S  
S%S    d*S        S%S SSSS%S             S&S             S%S SSSS%S  
S&S   .S*S        S&S  SSS%S             S&S             S&S  SSS&S  
S&S_sdSSS         S&S    S&S             S&S             S&S    S&S  
S&S~YSSY          S&S    S&S             S&S             S&S    S&S  
S*S               S*S    S&S             S*S             S*S    S*S  
S*S               S*S    S*S             S*S             S*S    S*S  
S*S               S*S    S*S             S*S             S*S    S*S  
S*S               SSS    S*S             S*S             SSS    S*S  
SP                       SP              SP                     SP   
Y                        Y               Y                      Y    
                                                                       [0m

        PATH — OSINT & IDENTITY INTELLIGENCE
                         v{version}
"""


def print_banner():
    from core import __version__
    print(BANNER.replace("{version}", __version__))
def print_report(report):
    print(f"Target: {report.target}")
    print("────────────────────────────────────────")
    print(f"Findings: {len(report.findings)}")

    if not report.findings:
        print("\n[-] No public findings.")
        return

    regular_findings = []
    social_profiles = []
    correlations = []
    personal_emails = []
    technical_emails = []
    test_emails = []

    for finding in report.findings:
        if finding.kind in ("correlation", "correlation_unmatched"):
            correlations.append(finding)
            continue

        if finding.kind in ("social", "linked_social"):
            social_profiles.append(finding)
            continue

        if finding.kind != "email":
            regular_findings.append(finding)
            continue

        if finding.classification == "personal_candidate":
            personal_emails.append(finding)

        elif finding.classification == "technical":
            technical_emails.append(finding)

        elif finding.classification == "test":
            test_emails.append(finding)

        else:
            regular_findings.append(finding)

    if correlations:
        print("\nCORRELATION (are these the same person?)")
        print("────────────────────────────────────────")
        for finding in correlations:
            label = "SAME PERSON?" if finding.kind == "correlation" else "UNCONFIRMED"
            print(f"\n[{finding.confidence.upper()}] {label}: {finding.value}")
            print(f"  Evidence:    {finding.evidence}")

    if social_profiles:
        rank = {"high": 0, "medium": 1, "low": 2}
        social_profiles.sort(key=lambda f: rank.get(f.confidence, 3))
        print("\nSOCIAL PROFILES")
        print("────────────────────────────────────────")

        for finding in social_profiles:
            print(f"\n[{finding.confidence.upper()}] {finding.value}")
            print(f"  Source:      {finding.source}")
            print(f"  Evidence:    {finding.evidence}")

    if personal_emails:
        print("\nPERSONAL CANDIDATES")
        print("────────────────────────────────────────")

        for finding in personal_emails:
            print(
                f"\n[{finding.confidence.upper()}] EMAIL"
            )
            print(f"  Address:     {finding.value}")
            print(f"  Provider:    {finding.provider}")
            print(f"  Source:      {finding.source}")
            print(f"  Source type: {finding.source_type}")
            print(f"  Evidence:    {finding.evidence}")

    if technical_emails:
        print("\nTECHNICAL EMAILS")
        print("────────────────────────────────────────")

        for finding in technical_emails:
            print(
                f"\n[{finding.confidence.upper()}] EMAIL"
            )
            print(f"  Address:     {finding.value}")
            print(f"  Provider:    {finding.provider}")
            print(f"  Source:      {finding.source}")
            print(f"  Source type: {finding.source_type}")

    if test_emails:
        print("\nTEST EMAILS")
        print("────────────────────────────────────────")

        for finding in test_emails:
            print(
                f"\n[INFO] EMAIL"
            )
            print(f"  Address:     {finding.value}")
            print(f"  Provider:    {finding.provider}")
            print(f"  Source:      {finding.source}")

    if regular_findings:
        print("\nOTHER FINDINGS")
        print("────────────────────────────────────────")

        for finding in regular_findings:
            print(
                f"\n[{finding.confidence.upper()}] "
                f"{finding.kind.upper()}"
            )
            print(f"  Value:       {finding.value}")
            print(f"  Source:      {finding.source}")
            print(f"  Source type: {finding.source_type}")
            print(f"  Evidence:    {finding.evidence}")