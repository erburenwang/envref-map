"""Command-line interface for the EnvRef Map scanner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from envref_map.project_scan import scan_project
from envref_map.report import render_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="envref-map",
        description="Map static environment-variable references to safe example templates.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="scan a project without changing it")
    scan.add_argument("--root", type=Path, default=Path.cwd(), help="project root (default: current directory)")
    scan.add_argument(
        "--template", type=Path, action="append", default=[], metavar="PATH",
        help="include a custom example template; may be repeated",
    )
    scan.add_argument("--format", choices=("text", "markdown", "json"), default="text", help="report format")
    scan.add_argument("--strict", action="store_true", help="return 1 when any referenced key is missing")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)

    try:
        report = scan_project(arguments.root, arguments.template)
    except OSError:
        print("envref-map: scan failed (operating_system_error)", file=sys.stderr)
        return 1
    except ValueError as error:
        # The scanner's validation errors are deliberately path-free so an
        # unsafe custom path cannot expose an absolute local path in output.
        print(f"envref-map: {error}", file=sys.stderr)
        return 1

    sys.stdout.write(render_report(report, arguments.format))
    if report.diagnostics:
        return 1
    if arguments.strict and any(item.status == "missing" for item in report.keys):
        return 1
    return 0
