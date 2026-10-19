import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import engine
from core.config import load_config
from core.models import Finding, new_report
from sources import breaches


def fake(body, status=200, ok=True):
    return {"ok": ok, "status": status, "final_url": "x", "headers": {},
            "data": body, "truncated": False, "error": None if ok else f"HTTP {status}"}


PAYLOAD = {"ExposedBreaches": {"breaches_details": [
    {"breach": "Alpha", "domain": "alpha.example", "xposed_date": "2019",
     "xposed_data": "Email addresses;Passwords", "xposed_records": 1000},
    {"breach": "Beta", "xposed_date": "2021", "xposed_data": "Usernames"},
    {"domain": "nameless.example"},
]}}


class Source(unittest.TestCase):
    def setUp(self):
        load_config(overrides={"cache": {"enabled": False}})

    def test_found(self):
        with mock.patch("sources.breaches.fetch", return_value=fake(json.dumps(PAYLOAD).encode())) as call:
            result = breaches.check_email("a+b@boba.dev")
        self.assertIn("a%2Bb@boba.dev", call.call_args[0][0])
        self.assertEqual(result["status"], "found")
        self.assertEqual([b["name"] for b in result["breaches"]], ["Alpha", "Beta"])
        self.assertEqual(result["breaches"][0]["classes"], ["Email addresses", "Passwords"])

    def test_none_limited_error(self):
        empty = {"ExposedBreaches": None, "BreachesSummary": {"site": ""}}
        with mock.patch("sources.breaches.fetch", return_value=fake(json.dumps(empty).encode())):
            self.assertEqual(breaches.check_email("x@y.dev")["status"], "none")
        with mock.patch("sources.breaches.fetch", return_value=fake(b"", 404, False)):
            self.assertEqual(breaches.check_email("x@y.dev")["status"], "none")
        with mock.patch("sources.breaches.fetch", return_value=fake(b"", 429, False)):
            self.assertEqual(breaches.check_email("x@y.dev")["status"], "limited")
        with mock.patch("sources.breaches.fetch", return_value=fake(b"", 500, False)):
            self.assertEqual(breaches.check_email("x@y.dev")["status"], "error")
        with mock.patch("sources.breaches.fetch", return_value=fake(b"not json")):
            self.assertEqual(breaches.check_email("x@y.dev")["status"], "error")

    def test_stops_after_rate_limit(self):
        with mock.patch("sources.breaches.fetch", return_value=fake(b"", 429, False)) as call, \
             mock.patch("sources.breaches.time.sleep"):
            result = breaches.check_emails(["a@x.dev", "b@x.dev", "c@x.dev"])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(list(result), ["a@x.dev"])


class Engine(unittest.TestCase):
    def report(self):
        r = new_report("boba")
        r.findings = [
            Finding(kind="email", value="me@boba.dev", source="https://boba.dev/", evidence="e",
                    classification="personal_candidate"),
            Finding(kind="email", value="noreply@boba.dev", source="https://boba.dev/", evidence="e",
                    classification="technical"),
        ]
        return r

    def test_disabled_by_default(self):
        load_config(overrides={"cache": {"enabled": False}})
        with mock.patch("sources.breaches.check_emails") as call:
            engine._add_breach_findings(self.report())
            call.assert_not_called()

    def test_adds_finding_for_personal_only(self):
        load_config(overrides={"cache": {"enabled": False}, "breaches": {"enabled": True}})
        result = {"me@boba.dev": {"status": "found", "breaches": [
            {"name": "Alpha", "domain": "", "year": "2019", "classes": ["Passwords"], "records": None}]}}
        r = self.report()
        with mock.patch("sources.breaches.check_emails", return_value=result) as call:
            engine._add_breach_findings(r)
        self.assertEqual(call.call_args[0][0], ["me@boba.dev"])
        found = [f for f in r.findings if f.kind == "breach"]
        self.assertEqual(len(found), 1)
        self.assertIn("Alpha (2019)", found[0].value)
        self.assertIn("Passwords", found[0].evidence)
        self.assertEqual(found[0].source_type, "breach_index")


if __name__ == "__main__":
    unittest.main()
