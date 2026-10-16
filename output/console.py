BANNER = r"""
[31m                                   s                
                                 :8      .uef^"    
    .d``                        .88    :d88E       
    @8Ne.   .u         u       :888ooo `888E       
    %8888:u@88N     us888u.  -*8888888  888E .z8k  
     `888I  888. .@88 "8888"   8888     888E~?888L 
      888I  888I 9888  9888    8888     888E  888E 
      888I  888I 9888  9888    8888     888E  888E 
    uW888L  888' 9888  9888   .8888Lu=  888E  888E 
   '*88888Nu88P  9888  9888   ^%888*    888E  888E 
   ~ '88888F`    "888*""888"    'Y"    m888N= 888> 
      888 ^       ^Y"   ^Y'             `Y"   888  
      *8E                                    J88"  
      '8>                                    @%    
       "                                   :"       [0m

        PATH — OSINT & IDENTITY INTELLIGENCE
                         v{version}
                     {author}
"""


def print_banner():
    from core import __version__
    author = "By \033[38;5;88mPath_Team\033[0m"
    print(BANNER.replace("{version}", __version__).replace("{author}", author))
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