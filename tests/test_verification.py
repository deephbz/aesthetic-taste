from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from executable_reports.app import main, parser
from executable_reports.artifacts import HTML, VERIFY_RECEIPT, VERIFY_SCREENSHOT
from executable_reports.verification import (
    build_verification_receipt,
    serve_report,
    verify_report,
)


class ReportHelpTests(unittest.TestCase):
    @staticmethod
    def help_text(arguments: list[str]) -> str:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), unittest.TestCase().assertRaises(SystemExit):
            parser().parse_args(arguments)
        return stdout.getvalue()

    def test_root_help_distinguishes_inspect_and_verify(self) -> None:
        help_text = self.help_text(["--help"])
        self.assertIn("what did we build?", help_text)
        self.assertIn("does it work?", help_text)
        self.assertIn("report inspect", help_text)
        self.assertIn("report verify", help_text)

    def test_inspect_help_excludes_browser_execution(self) -> None:
        help_text = self.help_text(["inspect", "--help"])
        self.assertIn("execute JavaScript", help_text)
        self.assertIn("Use 'report verify'", help_text)

    def test_verify_help_names_receipt_and_diagnostic_surface(self) -> None:
        help_text = self.help_text(["verify", "--help"])
        self.assertIn(VERIFY_RECEIPT, help_text)
        self.assertIn(VERIFY_SCREENSHOT, help_text)
        self.assertIn("__REPORT_VERIFY__", help_text)
        self.assertIn("pre-1.0", help_text)
        self.assertIn("diagnostic API", help_text)


class VerificationReceiptTests(unittest.TestCase):
    @staticmethod
    def base_events() -> dict:
        return {
            "requests_total": 3,
            "responses_total": 3,
            "pending_requests": [],
            "console": [],
            "page_errors": [],
            "request_failures": [],
            "response_errors": [],
            "dialogs": [],
            "crashes": [],
        }

    @staticmethod
    def base_probe() -> dict:
        return {
            "page": {"ready_state": "complete", "title": "Report"},
            "document": {
                "elements": 8,
                "horizontal_overflow_px": 0,
                "allow_horizontal_overflow": False,
                "broken_images": [],
            },
            "overflow_elements": [],
            "views": [
                {
                    "selector": "[data-report-view=chart]",
                    "tag": "div",
                    "declared_view": True,
                    "visible": True,
                    "rect": {"width": 640, "height": 320},
                    "canvas": None,
                    "view_box": None,
                }
            ],
            "resources": [],
            "hook": {"present": False, "result": None, "error": None},
        }

    def build(self, *, events: dict | None = None, probe: dict | None = None) -> dict:
        return build_verification_receipt(
            target_sha256="abc",
            response_status=200,
            browser={"engine": "chromium", "version": "test"},
            events=events or self.base_events(),
            probe=probe or self.base_probe(),
            timing_ms={"total": 12},
            screenshot_path=VERIFY_SCREENSHOT,
            checked_at="2026-08-25T00:00:00+00:00",
        )

    def test_clean_observation_passes_with_bounded_agent_contract(self) -> None:
        receipt = self.build()
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["summary"]["errors"], 0)
        self.assertEqual(receipt["summary"]["views_observed"], 1)
        self.assertEqual(receipt["diagnostics"]["stability"], "internal-pre-1.0")
        self.assertIn("diagnose_problem", receipt["diagnostics"]["quick_start"])

        probe = self.base_probe()
        probe["page"]["url"] = "http://127.0.0.1:4567/report.rendered.html"
        normalized = self.build(probe=probe)
        self.assertEqual(normalized["page"]["url"], HTML)

    def test_console_error_and_layout_overflow_fail(self) -> None:
        events = self.base_events()
        events["console"] = [{"type": "error", "text": "boom", "location": {}}]
        probe = self.base_probe()
        probe["document"]["horizontal_overflow_px"] = 120
        probe["overflow_elements"] = [{"selector": "#wide", "right_overflow": 120}]
        receipt = self.build(events=events, probe=probe)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["summary"]["errors"], 2)
        self.assertEqual(
            [problem["id"] for problem in receipt["problems"]],
            ["runtime.console-error.1", "layout.document-overflow-x"],
        )
        self.assertIn("diagnose_problem", receipt["problems"][1]["diagnostic_api"])
        self.assertIn("whole-document overflow scan", receipt["problems"][1]["evidence"]["next"])

    def test_warning_does_not_fail_fast_acceptance(self) -> None:
        events = self.base_events()
        events["console"] = [{"type": "warning", "text": "deprecated", "location": {}}]
        receipt = self.build(events=events)
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["summary"]["warnings"], 1)

    def test_report_hook_can_add_targeted_checks(self) -> None:
        probe = self.base_probe()
        probe["hook"] = {
            "present": True,
            "error": None,
            "result": {
                "status": "failed",
                "checks": [
                    {
                        "name": "row count",
                        "status": "failed",
                        "message": "expected 10 rows, observed 0",
                        "selector": "#grid",
                    }
                ],
            },
        }
        receipt = self.build(probe=probe)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["problems"][0]["category"], "report_hook")
        self.assertEqual(receipt["problems"][0]["selector"], "#grid")

    def test_visible_zero_bitmap_canvas_fails(self) -> None:
        probe = self.base_probe()
        probe["views"][0].update(
            {
                "tag": "canvas",
                "canvas": {"bitmap_width": 0, "bitmap_height": 0},
            }
        )
        receipt = self.build(probe=probe)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["problems"][0]["id"], "views.canvas-zero-bitmap.1")


class StaticReportServerTests(unittest.TestCase):
    def test_loopback_server_serves_report_and_browser_mime_types(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / HTML).write_text("<h1>Report</h1>", encoding="utf-8")
            (root / "data.arrow").write_bytes(b"arrow")
            (root / "module.wasm").write_bytes(b"wasm")
            with serve_report(root) as url:
                with urllib.request.urlopen(url) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                arrow_url = url.rsplit("/", 1)[0] + "/data.arrow"
                with urllib.request.urlopen(arrow_url) as response:
                    self.assertEqual(
                        response.headers.get_content_type(),
                        "application/vnd.apache.arrow.file",
                    )
                request = urllib.request.Request(arrow_url, headers={"Range": "bytes=1-3"})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.headers["Content-Range"], "bytes 1-3/5")
                    self.assertEqual(response.read(), b"rro")
                with urllib.request.urlopen(url.rsplit("/", 1)[0] + "/module.wasm") as response:
                    self.assertEqual(response.headers.get_content_type(), "application/wasm")


class VerifyCommandTests(unittest.TestCase):
    @staticmethod
    def failed_receipt() -> dict:
        return {
            "schema_version": 1,
            "kind": "executable_report_browser_verification",
            "status": "failed",
            "summary": {"errors": 1, "warnings": 0},
            "problems": [
                {
                    "id": "layout.document-overflow-x",
                    "category": "layout",
                    "severity": "error",
                    "message": "document is 90px wider than the viewport",
                    "selector": "#wide",
                }
            ],
            "evidence": {"screenshot": None},
            "diagnostics": {
                "quick_start": "from executable_reports.verification import diagnose_problem"
            },
        }

    def test_verify_writes_receipt_screenshot_and_bootstrap_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / HTML).write_text("<h1>Report</h1>", encoding="utf-8")

            def fake_verify(_root: Path, **kwargs: object) -> dict:
                Path(kwargs["screenshot_path"]).write_bytes(b"png")  # type: ignore[index]
                return self.failed_receipt()

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch("executable_reports.app.verify_report", side_effect=fake_verify),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = main(["verify", str(root)])

            self.assertEqual(result, 1)
            receipt = json.loads((root / VERIFY_RECEIPT).read_text(encoding="utf-8"))
            self.assertEqual(receipt["evidence"]["screenshot"], VERIFY_SCREENSHOT)
            self.assertEqual(receipt["evidence"]["screenshot_bytes"], 3)
            self.assertEqual(len(receipt["evidence"]["screenshot_sha256"]), 64)
            self.assertTrue((root / VERIFY_SCREENSHOT).is_file())
            self.assertEqual(json.loads(stdout.getvalue())["status"], "failed")
            self.assertIn("layout.document-overflow-x", stderr.getvalue())
            self.assertIn("diagnose_problem", stderr.getvalue())

    def test_verify_setup_error_still_writes_a_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / HTML).write_text("<h1>Report</h1>", encoding="utf-8")
            receipt = self.failed_receipt()
            receipt["status"] = "error"
            receipt["problems"][0]["id"] = "setup.browser"
            with (
                mock.patch("executable_reports.app.verify_report", return_value=receipt),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = main(["verify", str(root)])
            self.assertEqual(result, 1)
            self.assertEqual(
                json.loads((root / VERIFY_RECEIPT).read_text(encoding="utf-8"))["status"],
                "error",
            )


@unittest.skipUnless(
    os.environ.get("REPORT_BROWSER_PATH"),
    "set REPORT_BROWSER_PATH for browser smoke",
)
class BrowserVerificationSmokeTests(unittest.TestCase):
    def test_static_report_runs_generic_and_report_owned_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / HTML).write_text(
                """<!doctype html>
<html><head><meta charset='utf-8'><title>Smoke</title></head>
<body><main><div data-report-view='chart' style='width:640px;height:240px'>ready</div></main>
<script>
window.__REPORT_VERIFY__ = async () => ({
  status: 'passed',
  checks: [{name: 'semantic ready', status: 'passed'}]
});
</script></body></html>""",
                encoding="utf-8",
            )
            screenshot = root / "smoke.png"
            receipt = verify_report(
                root,
                browser_path=os.environ["REPORT_BROWSER_PATH"],
                timeout_seconds=10,
                screenshot_path=screenshot,
            )
            self.assertEqual(receipt["status"], "passed", receipt)
            self.assertEqual(receipt["summary"]["views_observed"], 1)
            self.assertTrue(receipt["report_hook"]["present"])
            self.assertTrue(screenshot.is_file())


if __name__ == "__main__":
    unittest.main()
