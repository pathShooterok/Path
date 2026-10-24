import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import path as cli
from core import __version__, cache
from core.config import load_config, validate_config, DEFAULTS
from core.models import Finding, new_report
from output.console import print_report
from output.html_report import render_html
from output.summary import format_summary, summarize
from sources import profiles
import copy


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(argv)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def finding(kind, value, source="https://github.com/bob", evidence="e", **kw):
    return Finding(kind=kind, value=value, source=source, evidence=evidence, **kw)


class CLI(unittest.TestCase):
    def test_version(self):
        code, out, _ = run(["--version"])
        self.assertEqual(code, 0)
        self.assertIn(__version__, out)

    def test_empty_and_bad_targets(self):
        for target in ("", "   ", "x" * 200, "bad\x07name"):
            with self.subTest(target=target):
                code, _, err = run(["trace", target])
                self.assertEqual(code, 2)
                self.assertIn("[-]", err)

    def test_url_without_scheme_gets_https(self):
        seen = {}

        def scan(url):
            seen["url"] = url
            return new_report(url)

        with mock.patch.object(cli, "run_url_scan", side_effect=scan), mock.patch.object(cli, "print_banner"):
            code, _, _ = run(["-url", "example.com/page"])
        self.assertEqual(code, 0)
        self.assertEqual(seen["url"], "https://example.com/page")

    def test_invalid_config_is_reported_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"http": {"timeout": -1}, "trace": {"queries": []}}))
            code, _, err = run(["--config", str(bad), "trace", "bob"])
        self.assertEqual(code, 2)
        self.assertIn("http.timeout", err)
        self.assertIn("trace.queries", err)

    def test_missing_config_file(self):
        code, _, err = run(["--config", "/nonexistent/none.json", "trace", "bob"])
        self.assertEqual(code, 2)
        self.assertIn("Config not found", err)

    def test_keyboard_interrupt(self):
        with mock.patch.object(cli, "run_trace", side_effect=KeyboardInterrupt), \
             mock.patch.object(cli, "print_banner"):
            code, _, err = run(["trace", "bob"])
        self.assertEqual(code, 130)
        self.assertIn("Interrupted", err)

    def test_failure_returns_one(self):
        with mock.patch.object(cli, "run_trace", side_effect=RuntimeError("boom")), \
             mock.patch.object(cli, "print_banner"):
            code, _, err = run(["trace", "bob"])
        self.assertEqual(code, 1)
        self.assertIn("boom", err)

    def test_outputs_are_written_and_errors_reported(self):
        report = new_report("bob")
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(cli, "run_trace", return_value=report), mock.patch.object(cli, "print_banner"):
            json_path = Path(tmp) / "sub" / "r.json"
            html_path = Path(tmp) / "r.html"
            code, _, _ = run(["trace", "bob", "--json", str(json_path), "--html", str(html_path)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["version"], __version__)
            self.assertIn("<html", html_path.read_text(encoding="utf-8"))
            code, _, err = run(["trace", "bob", "--json", tmp])
            self.assertEqual(code, 1)
            self.assertIn("Could not save", err)

    def test_clear_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_config(overrides={"cache": {"enabled": True, "dir": tmp + "/c"}})
            cache.store("https://a.example/", None, {"ok": True, "status": 200, "final_url": "x",
                                                     "headers": {}, "data": b"hi", "truncated": False})
            self.assertIsNotNone(cache.load("https://a.example/", None))
            with mock.patch("path.load_config", return_value=None), \
                 mock.patch("path.get_config", return_value={"cache": {"dir": tmp + "/c"}}):
                code, out, _ = run(["--clear-cache"])
            self.assertEqual(code, 0)
            self.assertIn("1 entries", out)
            self.assertIsNone(cache.load("https://a.example/", None))

    def test_clear_cache_never_touches_foreign_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            keep = Path(tmp) / "notes.txt"
            keep.write_text("keep")
            nested = Path(tmp) / "docs" / "a.json"
            nested.parent.mkdir()
            nested.write_text("{}")
            load_config(overrides={"cache": {"dir": tmp}})
            self.assertEqual(cache.clear(), 0)
            self.assertTrue(keep.exists() and nested.exists())


class ConfigValidation(unittest.TestCase):
    def test_defaults_are_valid(self):
        self.assertEqual(validate_config(copy.deepcopy(DEFAULTS)), [])

    def test_catches_type_and_range_mistakes(self):
        cfg = copy.deepcopy(DEFAULTS)
        cfg["http"]["retries"] = 1.5
        cfg["cache"]["enabled"] = "yes"
        cfg["profiles"]["platforms"] = "GitHub"
        cfg["trace"]["min_profile_match"] = "close"
        cfg["profiles"]["workers"] = True
        text = " ".join(validate_config(cfg))
        for key in ("http.retries", "cache.enabled", "profiles.platforms", "min_profile_match", "profiles.workers"):
            self.assertIn(key, text)


class Probes(unittest.TestCase):
    def test_blocked_label(self):
        label = profiles._api_label({"ok": False, "status": 403, "error": "HTTP 403: Forbidden"}, False)
        self.assertIn("blocked", label)
        self.assertTrue(profiles._api_label({"ok": False, "status": 500, "error": "HTTP 500"}, False).startswith("?"))
        self.assertEqual(profiles._api_label({"ok": False, "status": 404, "error": "x"}, False), "-")

    def test_codeberg_is_not_probed_by_default(self):
        self.assertNotIn("Codeberg", DEFAULTS["profiles"]["platforms"])
        self.assertIn("Codeberg", profiles.PROBES)


class Summary(unittest.TestCase):
    def report(self):
        r = new_report("bob")
        r.findings = [
            finding("social", "GitHub: https://github.com/bob"),
            finding("linked_social", "GitHub: https://github.com/Bob"),
            finding("social", "X: https://x.com/bob"),
            finding("email", "a@b.dev"), finding("email", "A@b.dev"),
            finding("name", "Bob B"),
            finding("link", "https://bob.dev", evidence="Website from GitHub public profile"),
            finding("correlation", "GitHub, X"),
        ]
        return r

    def test_counts(self):
        counts = summarize(self.report())
        self.assertEqual(counts, {"profiles": 2, "emails": 1, "names": 1, "websites": 1,
                                  "breaches": 0, "same_person_groups": 1})
        self.assertEqual(format_summary(counts),
                         "2 profiles, 1 email, 1 name, 1 website, 1 likely same-person group")
        self.assertEqual(format_summary(summarize(new_report("x"))), "")

    def test_shown_in_console_and_html(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            print_report(self.report())
        self.assertIn("Summary:  2 profiles", buffer.getvalue())
        self.assertIn("Summary: 2 profiles", render_html(self.report()))


if __name__ == "__main__":
    unittest.main()
