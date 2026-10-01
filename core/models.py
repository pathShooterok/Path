from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json


@dataclass
class Finding:
    kind: str
    value: str
    source: str
    evidence: str
    confidence: str = "low"
    source_type: str = "unknown"
    provider: str = ""
    classification: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class Report:
    target: str
    started_at: str
    findings: list[Finding]

    def to_json(self):
        return json.dumps(
            {
                "target": self.target,
                "started_at": self.started_at,
                "findings": [
                    finding.to_dict()
                    for finding in self.findings
                ],
            },
            ensure_ascii=False,
            indent=2,
        )


def new_report(target: str) -> Report:
    return Report(
        target=target,
        started_at=datetime.now(timezone.utc).isoformat(),
        findings=[],
    )