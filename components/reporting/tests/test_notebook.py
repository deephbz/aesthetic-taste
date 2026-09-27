from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from executable_reports import notebook
from executable_reports.app import parser


class FakeModel:
    def __init__(self) -> None:
        self.cells = [
            {
                "id": "setup-id",
                "cell_type": "code",
                "source": "x = 1\n",
                "metadata": {"collaboration": {"stable_name": "setup"}},
                "execution_count": 1,
                "outputs": [],
                "execution_state": "idle",
            },
            {
                "id": "notes-id",
                "cell_type": "markdown",
                "source": "# Notes\n",
                "metadata": {},
                "attachments": {"image/png": {"pixel.png": "AA=="}},
                "execution_count": None,
                "outputs": [],
            },
        ]
        self.metadata = {
            "kernelspec": {
                "name": "python3",
                "display_name": "Python 3",
                "language": "python",
            }
        }

    def __len__(self) -> int:
        return len(self.cells)

    def __getitem__(self, index: int) -> dict:
        return self.cells[index]

    def get_cell_metadata(self, index: int, key: str, default: object = None) -> object:
        return self.cells[index].get("metadata", {}).get(key, default)

    def get_cell_source(self, index: int) -> str:
        return self.cells[index]["source"]


class NotebookPureTests(unittest.TestCase):
    def test_server_url_removes_query_and_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "server.json"
            path.write_text(
                json.dumps({"url": "http://127.0.0.1:8888/lab/?token=secret#page", "token": "secret"}),
                encoding="utf-8",
            )
            config = notebook.read_server(path)
        self.assertEqual(config.url, "http://127.0.0.1:8888/lab")

    def test_server_url_rejects_userinfo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "server.json"
            path.write_text(
                json.dumps({"url": "http://user:password@127.0.0.1:8888", "token": "secret"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(notebook.NotebookError, "username or password"):
                notebook.read_server(path)

    def test_cell_selector_accepts_index_native_id_and_stable_name(self) -> None:
        model = FakeModel()
        self.assertEqual(notebook.cell_index(model, "0"), 0)
        self.assertEqual(notebook.cell_index(model, "notes-id"), 1)
        self.assertEqual(notebook.cell_index(model, "setup"), 0)
        with self.assertRaisesRegex(notebook.NotebookError, "not found"):
            notebook.cell_index(model, "missing")

    def test_serialised_cell_reports_unknown_execution_hash_as_unknown(self) -> None:
        cell = notebook.serialise_cell(FakeModel(), 0)
        self.assertEqual(cell["source_sha256"], notebook.sha256_text("x = 1\n"))
        self.assertIsNone(cell["executed_source_sha256"])
        self.assertIsNone(cell["source_executed_hash_mismatch"])

    def test_native_snapshot_preserves_ids_source_and_metadata(self) -> None:
        snapshot = notebook.notebook_snapshot(FakeModel())
        self.assertEqual(snapshot["cells"][0]["id"], "setup-id")
        self.assertEqual(snapshot["cells"][1]["source"], "# Notes\n")
        self.assertEqual(snapshot["metadata"]["kernelspec"]["name"], "python3")
        self.assertEqual(snapshot["nbformat"], 4)
        self.assertNotIn("execution_state", snapshot["cells"][0])
        self.assertEqual(snapshot["cells"][1]["attachments"]["image/png"]["pixel.png"], "AA==")

    def test_legacy_cell_without_id_gets_id_only_at_native_export(self) -> None:
        model = FakeModel()
        model.cells[1].pop("id")
        snapshot = notebook.notebook_snapshot(model)
        self.assertNotIn("id", snapshot["cells"][1])
        try:
            import nbformat
        except ImportError:
            self.skipTest("nbformat is not installed")
        native = notebook._native_notebook(snapshot)
        nbformat.validate(native)
        self.assertTrue(native.cells[1].id)

    def test_snapshot_is_accepted_by_jupytext_when_extra_is_installed(self) -> None:
        try:
            import jupytext
            import nbformat
        except ImportError:
            self.skipTest("notebook export dependencies are not installed")
        text = jupytext.writes(
            nbformat.from_dict(notebook.notebook_snapshot(FakeModel())),
            fmt="py:percent",
        )
        nbformat.validate(nbformat.from_dict(notebook.notebook_snapshot(FakeModel())))
        self.assertIn("x = 1", text)

    def test_source_can_come_from_file_or_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.py"
            path.write_text("print(1)\n", encoding="utf-8")
            args = argparse.Namespace(source=None, source_file=str(path))
            self.assertEqual(notebook._source_from_args(args), "print(1)\n")
        args = argparse.Namespace(source=None, source_file="-")
        with mock.patch("sys.stdin", io.StringIO("print(2)\n")):
            self.assertEqual(notebook._source_from_args(args), "print(2)\n")

    def test_export_refuses_live_notebook_path(self) -> None:
        args = argparse.Namespace(notebook="demo.ipynb", output="./demo.ipynb")
        with self.assertRaisesRegex(notebook.NotebookError, "overwrite"):
            notebook._output_path(args)

    def test_export_resolves_server_root_before_overwrite_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "report.ipynb"
            live.write_text("{}", encoding="utf-8")
            args = argparse.Namespace(notebook="report.ipynb", output=str(live))
            config = notebook.ServerConfig("http://127.0.0.1:8888", "secret", root)
            with self.assertRaisesRegex(notebook.NotebookError, "overwrite"):
                notebook._output_path(args, config)

    def test_unknown_server_root_rejects_matching_output_basename(self) -> None:
        args = argparse.Namespace(notebook="report.ipynb", output="/tmp/another/report.ipynb")
        with self.assertRaisesRegex(notebook.NotebookError, "overwrite"):
            notebook._output_path(args, notebook.ServerConfig("http://127.0.0.1:8888", "secret"))

    def test_missing_live_extra_names_recommended_command(self) -> None:
        with mock.patch.dict("sys.modules", {"requests": None}):
            with self.assertRaisesRegex(notebook.NotebookError, "--extra notebook"):
                notebook._optional_dependencies()

    def test_text_export_result_does_not_treat_cell_count_as_cells(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            notebook._emit(
                {
                    "notebook": "report.ipynb",
                    "output": "snapshot.ipynb",
                    "format": "ipynb",
                    "cells": 7,
                },
                "text",
            )
        self.assertIn("Exported ipynb snapshot: snapshot.ipynb", stdout.getvalue())

    def test_text_execution_output_is_bounded_to_a_summary(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            notebook._emit(
                {
                    "notebook": "report.ipynb",
                    "kernel_id": "kernel",
                    "status": "ok",
                    "results": [
                        {
                            "cell": {"index": 1, "id": "bokeh"},
                            "result": {
                                "status": "ok",
                                "outputs": [
                                    {
                                        "output_type": "display_data",
                                        "data": {"text/html": "x"},
                                    }
                                ],
                            },
                            "source_executed_hash_mismatch": False,
                        }
                    ],
                },
                "text",
            )
        self.assertIn("MIME text/html", stdout.getvalue())
        self.assertNotIn('"text/html"', stdout.getvalue())


class NotebookCliContractTests(unittest.TestCase):
    def test_notebook_commands_are_nested_under_report(self) -> None:
        root = parser()
        for operation in ("status", "read", "insert", "edit", "move", "delete", "execute", "eval", "export"):
            args = ["notebook", "--server-json", "server.json", operation]
            if operation == "insert":
                args.extend(["--source", "x = 1"])
            elif operation == "edit":
                args.extend(["--cell", "setup", "--source", "x = 2"])
            elif operation == "move":
                args.extend(["--cell", "setup", "--to", "1"])
            elif operation == "delete":
                args.extend(["--cell", "setup"])
            elif operation == "execute":
                args.extend(["--cell", "setup"])
            elif operation == "eval":
                args.extend(["--scratch", "--code", "1 + 1"])
            elif operation == "export":
                args.extend(["--format", "ipynb", "--output", "snapshot.ipynb"])
            parsed = root.parse_args(args)
            self.assertEqual(parsed.operation, operation)
            self.assertEqual(parsed.handler, notebook.command)


class NotebookCloseTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_close_reports_stop_failure(self) -> None:
        class FailingModel:
            async def stop(self) -> None:
                raise RuntimeError("flush failed")

        with self.assertRaisesRegex(notebook.NotebookError, "unconfirmed"):
            await notebook._close_model(FailingModel(), 1)

    async def test_normal_close_reports_stop_timeout(self) -> None:
        class HangingModel:
            async def stop(self) -> None:
                await asyncio.sleep(1)

        with self.assertRaisesRegex(notebook.NotebookError, "timed out"):
            await notebook._close_model(HangingModel(), 0.01)


if __name__ == "__main__":
    unittest.main()
