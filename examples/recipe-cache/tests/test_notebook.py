"""Run example.py as a notebook in fresh kernels, the way a restarted session does."""
import json
import sys
from pathlib import Path

import jupytext
import pytest
from nbclient import NotebookClient

EXAMPLE = Path(__file__).parents[1] / "example.py"


@pytest.fixture
def kernel(tmp_path, monkeypatch):
    """A kernelspec for this interpreter, so the kernel imports this project."""
    spec = tmp_path / "jupyter" / "kernels" / "recipe-cache"
    spec.mkdir(parents=True)
    spec.joinpath("kernel.json").write_text(json.dumps({
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "recipe-cache", "language": "python"}))
    monkeypatch.setenv("JUPYTER_PATH", str(tmp_path / "jupyter"))
    monkeypatch.setenv("RECIPE_CACHE_EXAMPLE", str(tmp_path / "work"))
    return "recipe-cache"


def run(kernel, source):
    notebook = jupytext.reads(source, fmt="py:percent")
    NotebookClient(notebook, kernel_name=kernel, timeout=120,
                   resources={"metadata": {"path": str(EXAMPLE.parent)}}).execute()
    reports = [line for cell in notebook.cells for output in cell.get("outputs", [])
               if output.get("name") == "stderr" for line in output["text"].splitlines()
               if line.startswith("recipe-cache")]
    return reports


def test_restarted_kernels_reuse_and_cell_helper_edits_recompute(kernel):
    """Detects: notebook-defined helpers that cannot be identified across kernels."""
    source = EXAMPLE.read_text()
    first = run(kernel, source)
    second = run(kernel, source)
    edited = source.replace('(pl.col("px") * pl.col("qty"))', '(pl.col("px") * pl.col("qty") * 2)')
    third = run(kernel, edited)
    assert first[0].startswith("recipe-cache miss __main__:enrich")
    assert second[0].startswith("recipe-cache hit __main__:enrich")
    assert third[0].startswith("recipe-cache miss __main__:enrich")
    assert "helper __main__:notional changed" in third[0]
