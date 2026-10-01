import argparse

from core.engine import run_trace, run_url_scan
from output.console import print_banner, print_report


def main():
    parser = argparse.ArgumentParser(
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
        help="Trace a public username",
    )

    trace_parser.add_argument(
        "target",
        help="Username or identifier",
    )

    args = parser.parse_args()

    print_banner()

    if args.url:
        report = run_url_scan(args.url)
        print_report(report)
        return

    if args.command == "trace":
        report = run_trace(args.target)
        print_report(report)
        return

    parser.print_help()

if __name__ == "__main__":
    main()