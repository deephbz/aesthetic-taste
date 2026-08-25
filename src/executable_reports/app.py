"""Public CLI composition for executable reports."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

from . import cli
from .artifacts import VERIFY_RECEIPT, VERIFY_SCREENSHOT
from .inventory import sha256
from .verification import verify_report


def command_verify(args: argparse.Namespace) -> int:
    root = cli.project_root(args.root)
    if not root.is_dir():
        raise cli.ReportError(f"report project root is not a directory: {root}")

    pending_png = root / ".report.verify.next.png"
    pending_json = root / f".{VERIFY_RECEIPT}.next"
    final_png = root / VERIFY_SCREENSHOT
    final_json = root / VERIFY_RECEIPT
    pending_png.unlink(missing_ok=True)
    pending_json.unlink(missing_ok=True)

    receipt = verify_report(
        root,
        browser_path=args.browser,
        timeout_seconds=args.timeout,
        screenshot_path=pending_png,
    )
    evidence = receipt.setdefault("evidence", {})
    if pending_png.is_file():
        os.replace(pending_png, final_png)
        evidence.update(
            screenshot=VERIFY_SCREENSHOT,
            screenshot_scope="initial viewport",
            screenshot_bytes=final_png.stat().st_size,
            screenshot_sha256=sha256(final_png),
        )
    else:
        final_png.unlink(missing_ok=True)
        evidence.update(screenshot=None, screenshot_bytes=None, screenshot_sha256=None)

    pending_json.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    os.replace(pending_json, final_json)
    print(json.dumps(receipt, indent=2))

    if receipt.get("status") == "passed":
        return 0
    summary = receipt.get("summary", {})
    print(
        f"Browser verification {receipt.get('status')}: "
        f"{summary.get('errors', 0)} error(s), {summary.get('warnings', 0)} warning(s).",
        file=sys.stderr,
    )
    print(f"Receipt: {VERIFY_RECEIPT}", file=sys.stderr)
    if evidence.get("screenshot"):
        print(f"Viewport evidence: {VERIFY_SCREENSHOT}", file=sys.stderr)
    for problem in receipt.get("problems", [])[:3]:
        print(f"- {problem.get('id')}: {problem.get('message')}", file=sys.stderr)
    quick_start = receipt.get("diagnostics", {}).get("quick_start")
    if quick_start:
        print("Run the following from the report project root:", file=sys.stderr)
        print("Agent diagnostic API (internal, pre-1.0):", file=sys.stderr)
        print(f"  {quick_start}", file=sys.stderr)
    return 1


def _subcommands(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    return next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )


def parser() -> argparse.ArgumentParser:
    result = cli.parser()
    result.description = "Build, inspect, and verify static executable reports."
    result.epilog = (
        "Choose the observation boundary:\n"
        "  report inspect  answers 'what did we build?' from saved artifacts and parsed HTML.\n"
        "  report verify   answers 'does it work?' in a real Chromium browser."
    )
    subcommands = _subcommands(result)

    inspect = subcommands.choices["inspect"]
    inspect.description = (
        "Answer: what did we build?\n\n"
        "Inspect saved artifacts and parsed HTML. Do not execute JavaScript or measure browser layout."
    )
    inspect.epilog = (
        "Use 'report verify' for runtime JavaScript, resource loading, and rendered layout."
    )

    verify = subcommands.add_parser(
        "verify",
        help="run fast real-browser checks against the rendered report",
        description=(
            "Answer: does the rendered report work?\n\n"
            "Load report.rendered.html in headless Chromium and check runtime errors, failed "
            "resources, high-confidence layout failures, renderer roots, and an optional "
            "window.__REPORT_VERIFY__ hook."
        ),
        epilog=(
            "Requires the Python package 'playwright' plus Chrome/Chromium.\n"
            "Outputs: report.verify.json and report.verify.png.\n"
            "Failures include a pre-1.0 Python diagnostic API for selector inspection, "
            "targeted screenshots, traces, and library-specific browser queries."
        ),
    )
    verify.add_argument("root", nargs="?", default=".")
    verify.add_argument(
        "--browser",
        metavar="PATH",
        help="explicit Chrome/Chromium executable (or set REPORT_BROWSER_PATH)",
    )
    verify.add_argument(
        "--timeout",
        type=float,
        default=15,
        metavar="SECONDS",
        help="maximum browser setup and page-load time (default: 15)",
    )
    verify.set_defaults(handler=command_verify)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except cli.ReportError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
