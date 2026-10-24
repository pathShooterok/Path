import argparse
import re
import sys
from pathlib import Path

from core import __version__, cache
from core.config import get_config, load_config
from core.engine import run_trace, run_url_scan
from output.console import print_banner, print_report
from output.html_report import save_html

MAX_TARGET_LENGTH = 128
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _setup_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            continue


def _clean_target(value: str) -> str:
    target = (value or "").strip()
    if not target:
        raise ValueError("target must not be empty")
    if len(target) > MAX_TARGET_LENGTH:
        raise ValueError(f"target is too long (max {MAX_TARGET_LENGTH} characters)")
    if CONTROL_CHARS.search(target):
        raise ValueError("target must not contain control characters")
    return target


def _clean_url(value: str) -> str:
    url = (value or "").strip()
    if not url:
        raise ValueError("URL must not be empty")
    if CONTROL_CHARS.search(url):
        raise ValueError("URL must not contain control characters")
    if "://" not in url:
        url = "https://" + url
    return url


def _write(path: str, text: str, label: str) -> bool:
    try:
        target = Path(path)
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    except OSError as error:
        print(f"[-] Could not save {label} to {path}: {error}", file=sys.stderr)
        return False
    print(f"[*] {label} saved to {path}")
    return True


def _finish(report, json_out, html_out=None) -> int:
    print_report(report)
    ok = True
    if json_out == "-":
        print(report.to_json())
    elif json_out:
        print()
        ok = _write(json_out, report.to_json(), "JSON") and ok
    if html_out:
        from output.html_report import render_html
        ok = _write(html_out, render_html(report), "HTML report") and ok
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=argparse.SUPPRESS, help="Path to config.json")
    common.add_argument("--json", dest="json_out", metavar="FILE", default=argparse.SUPPRESS,
                        help="Also save the report as JSON (use - for stdout)")
    common.add_argument("--html", dest="html_out", metavar="FILE", default=argparse.SUPPRESS,
                        help="Also save the report as a self-contained HTML page")
    common.add_argument("--no-cache", action="store_true", default=argparse.SUPPRESS,
                        help="Do not use the on-disk request cache")
    common.add_argument("--raw", action="store_true", default=argparse.SUPPRESS,
                        help="Keep duplicates and junk: skip the report cleanup")
    common.add_argument("--breaches", action="store_true", default=argparse.SUPPRESS,
                        help="Check found personal emails against the public XposedOrNot breach index")
    common.add_argument("--no-breaches", action="store_true", default=argparse.SUPPRESS,
                        help="Do not send found emails to the breach index")
    common.add_argument("--no-probe", "--no-profile-probes", dest="no_probe", action="store_true",
                        default=argparse.SUPPRESS, help="Do not query platforms directly for the username")
    common.add_argument("--no-profiles", "--no-profile-pages", dest="no_profiles", action="store_true",
                        default=argparse.SUPPRESS, help="Do not fetch profile pages found in search results")

    parser = argparse.ArgumentParser(
        parents=[common],
        prog="path",
        description="Path — OSINT & Identity Intelligence",
    )
    parser.add_argument("-V", "--version", action="version", version=f"path {__version__}")
    parser.add_argument("-url", dest="url", help="Scan a public URL")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Delete the on-disk request cache and exit")

    subparsers = parser.add_subparsers(dest="command", required=False)
    trace_parser = subparsers.add_parser("trace", parents=[common], help="Trace a public username")
    trace_parser.add_argument("target", help="Username or identifier")
    trace_parser.add_argument(
        "--sources",
        help="Comma-separated sources to use, overrides config (duckduckgo,bing,google)",
    )
    return parser


def _overrides(args) -> dict:
    overrides = {}
    if getattr(args, "no_profiles", False):
        overrides["trace"] = {"scan_social_profiles": False}
    if getattr(args, "no_probe", False):
        overrides["profiles"] = {"enabled": False}
    if getattr(args, "breaches", False):
        overrides["breaches"] = {"enabled": True}
    if getattr(args, "no_breaches", False):
        overrides["breaches"] = {"enabled": False}
    if getattr(args, "raw", False):
        overrides["cleanup"] = {"enabled": False}
    if getattr(args, "no_cache", False):
        overrides["cache"] = {"enabled": False}
    return overrides


def main(argv: list[str] | None = None) -> int:
    _setup_output()
    parser = build_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1

    if args.url and args.command == "trace":
        parser.error("argument -url: not allowed with argument trace")

    if not args.url and args.command != "trace" and not args.clear_cache:
        parser.print_help()
        return 1

    try:
        load_config(getattr(args, "config", None), _overrides(args))
    except SystemExit as e:
        print(e.code, file=sys.stderr)
        return 2

    if args.clear_cache:
        removed = cache.clear()
        print(f"[*] Cache cleared ({removed} entries removed from {get_config()['cache']['dir']})")
        return 0

    try:
        if args.url:
            subject = _clean_url(args.url)
        else:
            subject = _clean_target(args.target)
            sources = getattr(args, "sources", None)
            only = [x.strip().lower() for x in sources.split(",") if x.strip()] if sources else None
    except ValueError as error:
        print(f"[-] {error}", file=sys.stderr)
        return 2

    print_banner()
    json_out = getattr(args, "json_out", None)
    html_out = getattr(args, "html_out", None)

    try:
        report = run_url_scan(subject) if args.url else run_trace(subject, only_sources=only)
    except KeyboardInterrupt:
        print("\n[-] Interrupted", file=sys.stderr)
        return 130
    except Exception as e:
        kind = "Scan" if args.url else "Trace"
        print(f"[-] {kind} failed: {e}", file=sys.stderr)
        return 1

    return _finish(report, json_out, html_out)


if __name__ == "__main__":
    sys.exit(main())
