from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from executable_reports.artifacts import HTML, INVENTORY, NOTEBOOK, QUARTO_CONFIG, SOURCE, STATIC
from executable_reports.cli import locate_quarto, main, promote_static_resources
from executable_reports.inventory import build_inventory, sha256


class ReportCliTests(unittest.TestCase):
    def write_artifacts(self, root: Path, *, execution_count: int | None = 1) -> dict:
        source = root / SOURCE
        source.write_text("# %%\nprint(41)\n", encoding="utf-8")
        source_hash = sha256(source)
        notebook = {
            "metadata": {
                "executable_report": {
                    "source": SOURCE,
                    "source_sha256": source_hash,
                }
            },
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": ["# Result"],
                    "metadata": {},
                },
                {
                    "cell_type": "code",
                    "source": ["print(41)"],
                    "metadata": {},
                    "execution_count": execution_count,
                    "outputs": [
                        {"output_type": "stream", "name": "stdout", "text": ["41\n"]}
                    ],
                },
            ],
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        (root / NOTEBOOK).write_text(json.dumps(notebook), encoding="utf-8")
        (root / HTML).write_text("<html><h1>Result</h1><p>41</p></html>", encoding="utf-8")
        return notebook

    def test_new_creates_only_authoritative_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sample-report"
            with contextlib.redirect_stdout(io.StringIO()):
                result = main(["new", str(root)])
            self.assertEqual(result, 0)
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                [QUARTO_CONFIG, "pyproject.toml", SOURCE],
            )
            self.assertNotIn("uv.lock", {path.name for path in root.iterdir()})
            self.assertIn("execute:\n  enabled: false", (root / QUARTO_CONFIG).read_text())

    def test_new_refuses_a_nonempty_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "unrelated.txt").write_text("keep", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main(["new", str(root)])
            self.assertEqual(result, 1)
            self.assertIn("requires an empty project root", stderr.getvalue())
            self.assertEqual((root / "unrelated.txt").read_text(), "keep")

    def test_inventory_links_source_notebook_and_html(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_artifacts(root)
            inventory = build_inventory(root, quarto_version="test")
            self.assertEqual(inventory["status"], "passed")
            self.assertNotIn("project_root", inventory)
            self.assertEqual(inventory["notebook"]["executed_code_cells"], 1)
            self.assertEqual(inventory["notebook"]["outputs"][0]["section"], "Result")
            self.assertEqual(inventory["html"]["headings"], [{"level": 1, "text": "Result"}])
            self.assertEqual(inventory["html"]["elements"], 3)
            self.assertEqual(inventory["html"]["tag_counts"]["p"], 1)
            self.assertEqual(inventory["html"]["section_elements"], [])
            self.assertGreater(inventory["notebook"]["output_bytes"], 0)

    def test_inventory_counts_nested_html_sections_as_contained_views(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_artifacts(root)
            (root / HTML).write_text(
                "<section id='outer'><h1>Outer</h1>"
                "<section id='inner'><h2>Inner</h2><p>x</p></section></section>",
                encoding="utf-8",
            )

            inventory = build_inventory(root, quarto_version="test")

            self.assertEqual(
                inventory["html"]["section_elements"],
                [
                    {"id": "outer", "title": "Outer", "elements": 5},
                    {"id": "inner", "title": "Inner", "elements": 3},
                ],
            )

    def test_inventory_warns_for_unexecuted_nonempty_code_but_ignores_empty_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            notebook = self.write_artifacts(root, execution_count=None)
            notebook["cells"].insert(
                1,
                {
                    "cell_type": "code",
                    "source": [""],
                    "execution_count": None,
                    "outputs": [],
                },
            )
            (root / NOTEBOOK).write_text(json.dumps(notebook), encoding="utf-8")
            inventory = build_inventory(root, quarto_version="test")
            self.assertEqual(inventory["status"], "warning")
            self.assertEqual(inventory["notebook"]["code_cells"], 1)
            self.assertEqual(inventory["notebook"]["unexecuted_code_cells"], 1)
            (root / INVENTORY).write_text(json.dumps(inventory), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = main(["inspect", str(root)])
            self.assertEqual(result, 1)
            inspected = json.loads(stdout.getvalue())
            self.assertEqual(inspected["status"], "warning")
            self.assertIn("1 unexecuted code cells", inspected["problems"][0])

    def test_inspect_warns_for_notebook_error_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            notebook = self.write_artifacts(root)
            notebook["cells"][1]["outputs"] = [
                {
                    "output_type": "error",
                    "ename": "ValueError",
                    "evalue": "bad value",
                    "traceback": [],
                }
            ]
            (root / NOTEBOOK).write_text(json.dumps(notebook), encoding="utf-8")
            inventory = build_inventory(root, quarto_version="test")
            (root / INVENTORY).write_text(json.dumps(inventory), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = main(["inspect", str(root)])
            self.assertEqual(result, 1)
            inspected = json.loads(stdout.getvalue())
            self.assertEqual(inspected["status"], "warning")
            self.assertIn("1 error outputs", inspected["problems"][0])

    def test_inspect_rejects_malformed_inventory_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / INVENTORY).write_text("{}", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main(["inspect", str(root)])
            self.assertEqual(result, 1)
            self.assertIn("ERROR: invalid report inventory", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_inspect_rejects_boolean_inventory_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_artifacts(root)
            inventory = build_inventory(root, quarto_version="test")
            inventory["notebook"]["code_cells"] = True
            (root / INVENTORY).write_text(json.dumps(inventory), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main(["inspect", str(root)])
            self.assertEqual(result, 1)
            self.assertIn("invalid report inventory", stderr.getvalue())

    def test_inspect_detects_changed_static_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_artifacts(root)
            static = root / STATIC
            static.mkdir()
            asset = static / "figure.svg"
            asset.write_text("known", encoding="utf-8")
            inventory = build_inventory(root, quarto_version="test")
            (root / INVENTORY).write_text(json.dumps(inventory), encoding="utf-8")
            asset.write_text("changed", encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = main(["inspect", str(root)])
            self.assertEqual(result, 1)
            inspected = json.loads(stdout.getvalue())
            self.assertIn(
                "report.static/figure.svg changed after inventory",
                inspected["problems"],
            )

    def test_inspect_defaults_to_json_and_can_render_human_html(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_artifacts(root)
            inventory = build_inventory(root, quarto_version="test")
            (root / INVENTORY).write_text(json.dumps(inventory), encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = main(["inspect", str(root), "--render"])

            self.assertEqual(result, 0)
            inspected = json.loads(stdout.getvalue())
            self.assertEqual(inspected["kind"], "executable_report_inspection")
            self.assertEqual(inspected["status"], "passed")
            self.assertEqual(inspected["human_projection"]["path"], "report.inspect.html")
            self.assertEqual(
                inspected["views"]["dimensions"]["html_structure"]["elements"],
                3,
            )
            rendered = (root / "report.inspect.html").read_text(encoding="utf-8")
            self.assertIn("Artifact size tree", rendered)
            self.assertIn("Parsed HTML elements by section", rendered)
            self.assertIn("Largest HTML tag groups", rendered)
            self.assertNotIn(str(root), rendered)

    def test_static_promotion_rewrites_resource_attributes_not_report_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sidecar = root / "report.executed_files"
            sidecar.mkdir()
            (sidecar / "asset.js").write_text("asset", encoding="utf-8")
            html = root / "report.rendered.next.html"
            html.write_text(
                '<script src="report.executed_files/asset.js"></script>'
                "<code>report.executed_files/asset.js</code>",
                encoding="utf-8",
            )

            promote_static_resources(root, html)

            rendered = html.read_text(encoding="utf-8")
            self.assertIn('src="report.static/asset.js"', rendered)
            self.assertIn("<code>report.executed_files/asset.js</code>", rendered)
            self.assertTrue((root / STATIC / "asset.js").is_file())

    def test_quarto_fallback_selects_newest_numeric_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            older = home / ".local/quarto/1.9.564/bin/quarto"
            newer = home / ".local/quarto/1.10.0/bin/quarto"
            for path in (older, newer):
                path.parent.mkdir(parents=True)
                path.write_text("", encoding="utf-8")
            with (
                mock.patch("executable_reports.cli.shutil.which", return_value=None),
                mock.patch("executable_reports.cli.Path.home", return_value=home),
            ):
                self.assertEqual(locate_quarto(None), newer)

    def test_render_passes_no_execute_to_quarto(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_artifacts(root)
            (root / QUARTO_CONFIG).write_text("format: html\n", encoding="utf-8")
            commands: list[list[str]] = []

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                if command[1:] == ["--version"]:
                    return subprocess.CompletedProcess(command, 0, "1.10.0\n", "")
                output = command[command.index("--output") + 1]
                (cwd / output).write_text("<html><h1>Result</h1></html>", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch("executable_reports.cli.locate_quarto", return_value=Path("/quarto")),
                mock.patch("executable_reports.cli.run_command", side_effect=fake_run),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = main(["render", str(root)])

            self.assertEqual(result, 0)
            render_command = next(command for command in commands if "render" in command)
            self.assertIn("--no-execute", render_command)

    def test_empty_root_argument_is_rejected(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main(["inspect", ""])
        self.assertEqual(result, 1)
        self.assertIn("project root cannot be empty", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
