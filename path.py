import argparse
import sys

from core.config import load_config
from core.engine import run_trace, run_url_scan
from output.console import print_banner, print_report


def _finish(report, json_out):
    print_report(report)
    if json_out == "-":
        print(report.to_json())
    elif json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            f.write(report.to_json())
        print(f"\n[*] JSON saved to {json_out}")


def main() -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=argparse.SUPPRESS, help="Path to config.json")
    common.add_argument("--json", dest="json_out", metavar="FILE", default=argparse.SUPPRESS,
                        help="Also save the report as JSON (use - for stdout)")
    common.add_argument("--no-profiles", action="store_true", default=argparse.SUPPRESS,
                        help="Do not fetch social profile pages during trace")

    parser = argparse.ArgumentParser(
        parents=[common],
        prog="path",
        description="Path — OSINT & Identity Intelligence",
    )

    parser.add_argument(
        "-url",
        dest="url",
        help="Scan a public URL",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=False,
    )

    trace_parser = subparsers.add_parser(
        "trace",
        parents=[common],
        help="Trace a public username",
    )

    trace_parser.add_argument(
        "target",
        help="Username or identifier",
    )
    trace_parser.add_argument(
        "--sources",
        help="Comma-separated sources to use, overrides config (duckduckgo,bing,google)",
    )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        return e.code

    # Check for conflicting arguments
    if args.url and args.command == "trace":
        parser.error("argument -url: not allowed with argument trace")

    if not args.url and args.command != "trace":
        parser.print_help()
        return 1

    args.config = getattr(args, "config", None)
    args.json_out = getattr(args, "json_out", None)
    args.no_profiles = getattr(args, "no_profiles", False)

    load_config(args.config, {"trace": {"scan_social_profiles": False}} if args.no_profiles else None)

    print_banner()

    if args.url:
        try:
            report = run_url_scan(args.url)
        except Exception as e:
            print(f"[-] Scan failed: {e}", file=sys.stderr)
            return 1
        _finish(report, args.json_out)
        return 0

    if args.command == "trace":
        try:
            only = [x.strip() for x in args.sources.split(",") if x.strip()] if args.sources else None
            report = run_trace(args.target, only_sources=only)
        except Exception as e:
            print(f"[-] Trace failed: {e}", file=sys.stderr)
            return 1
        _finish(report, args.json_out)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())