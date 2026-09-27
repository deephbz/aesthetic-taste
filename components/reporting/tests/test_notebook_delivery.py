from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from executable_reports.artifacts import HTML, INVENTORY, QUARTO_CONFIG, NOTEBOOK
from executable_reports.cli import main
from executable_reports.inventory import build_inventory, sha256


def notebook(*, metadata: dict | None = None, executed: bool = True) -> dict:
    return {
        "metadata": metadata or {},
        "cells": [
            {
                "cell_type": "code",
                "source": ["print('ok')\n"],
                "metadata": {},
                "execution_count": 1 if executed else None,
                "outputs": (
                    [{"output_type": "stream", "name": "stdout", "text": ["ok\n"]}]
                    if executed
                    else []
                ),
            }
        ],
        "nbformat": 4,
        "nbformat_minor": 5,
    }


class NotebookDeliveryTests(unittest.TestCase):
    def test_run_native_notebook_copies_input_and_selects_requested_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "research.ipynb"
            original = notebook(executed=False)
            source.write_text(json.dumps(original), encoding="utf-8")
            original_bytes = source.read_bytes()
            preexisting = root / ".report-kernel.next"
            preexisting.mkdir()
            sentinel = preexisting / "keep-me.txt"
            sentinel.write_text("preserve", encoding="utf-8")
            commands: list[tuple[list[str], dict[str, str] | None]] = []

            def fake_run(
                command: list[str], *, cwd: Path, env: dict[str, str] | None = None
            ) -> subprocess.CompletedProcess[str]:
                commands.append((command, env))
                if "nbconvert" in command:
                    input_path = cwd / command[command.index("--execute") + 1]
                    output_path = cwd / command[command.index("--output") + 1]
                    executed = json.loads(input_path.read_text(encoding="utf-8"))
                    executed["cells"][0]["execution_count"] = 1
                    executed["cells"][0]["outputs"] = [
                        {"output_type": "stream", "name": "stdout", "text": ["ok\n"]}
                    ]
                    output_path.write_text(json.dumps(executed), encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0, "", "")
                if "-c" in command:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        json.dumps({"executable": sys.executable, "python": "test"}) + "\n",
                        "",
                    )
                self.fail(f"unexpected command: {command}")

            with mock.patch("executable_reports.cli.run_command", side_effect=fake_run):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = main(
                        [
                            "run",
                            str(root),
                            "--python",
                            sys.executable,
                            "--source",
                            source.name,
                        ]
                    )

            self.assertEqual(result, 0)
            self.assertEqual(source.read_bytes(), original_bytes)
            output = json.loads((root / NOTEBOOK).read_text(encoding="utf-8"))
            execution = output["metadata"]["executable_report"]
            self.assertEqual(execution["source"], source.name)
            self.assertEqual(execution["source_sha256"], sha256(source))
            self.assertEqual(execution["source_kind"], "notebook")
            self.assertEqual(execution["execution_mode"], "clean")
            nbconvert = next(command for command, _ in commands if "nbconvert" in command)
            self.assertIn("--ExecutePreprocessor.kernel_name=executable-report-python", nbconvert)
            environment = next(env for command, env in commands if "nbconvert" in command)
            assert environment is not None
            self.assertIn(".report-kernel-", environment["JUPYTER_PATH"])
            self.assertTrue(sentinel.is_file())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")

    def test_render_native_notebook_preserves_input_and_marks_freshness_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / "session.ipynb"
            native_notebook = notebook()
            native_notebook["cells"][0]["source"] = "## heading\n\nparagraph\n"
            native.write_text(json.dumps(native_notebook), encoding="utf-8")
            original_bytes = native.read_bytes()
            (root / QUARTO_CONFIG).write_text("execute:\n  enabled: false\n", encoding="utf-8")
            commands: list[list[str]] = []
            projected_sources: list[object] = []

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                if command[1:] == ["--version"]:
                    return subprocess.CompletedProcess(command, 0, "1.10.0\n", "")
                projected = json.loads(
                    (cwd / "report.rendered.next.ipynb").read_text(encoding="utf-8")
                )
                projected_sources.append(projected["cells"][0]["source"])
                output = command[command.index("--output") + 1]
                (cwd / output).write_text("<html><h1>Session</h1></html>", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch("executable_reports.cli.locate_quarto", return_value=Path("/quarto")),
                mock.patch("executable_reports.cli.run_command", side_effect=fake_run),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = main(["render", str(root), "--notebook", native.name])

            self.assertEqual(result, 0)
            self.assertEqual(native.read_bytes(), original_bytes)
            inventory = json.loads((root / INVENTORY).read_text(encoding="utf-8"))
            self.assertEqual(inventory["notebook"]["path"], native.name)
            self.assertEqual(inventory["source"]["path"], native.name)
            self.assertEqual(inventory["source"]["sha256"], sha256(native))
            self.assertEqual(inventory["source"]["freshness"], "unknown")
            self.assertEqual(inventory["status"], "warning")
            self.assertEqual(projected_sources, [["## heading\n", "\n", "paragraph\n"]])
            self.assertTrue((root / HTML).is_file())
            self.assertFalse((root / "report.executed.ipynb").exists())

            inspect_stdout = io.StringIO()
            with contextlib.redirect_stdout(inspect_stdout):
                inspect_result = main(["inspect", str(root)])
            self.assertEqual(inspect_result, 1)
            self.assertIn("source freshness is unknown", inspect_stdout.getvalue())

    def test_inventory_uses_native_source_metadata_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.ipynb"
            source.write_text(json.dumps(notebook()), encoding="utf-8")
            metadata = {
                "executable_report": {
                    "source": source.name,
                    "source_sha256": sha256(source),
                    "execution_mode": "clean",
                }
            }
            rendered = root / "snapshot.ipynb"
            rendered.write_text(json.dumps(notebook(metadata=metadata)), encoding="utf-8")
            (root / HTML).write_text("<html></html>", encoding="utf-8")

            inventory = build_inventory(root, notebook_path=rendered.name, quarto_version="test")

            self.assertEqual(inventory["source"]["path"], source.name)
            self.assertEqual(inventory["source"]["sha256"], sha256(source))
            self.assertEqual(inventory["source"]["freshness"], "verified")
            self.assertEqual(inventory["notebook"]["path"], rendered.name)


if __name__ == "__main__":
    unittest.main()
