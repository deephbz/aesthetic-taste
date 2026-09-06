"""Command-line interface for the executable-report vertical slice."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from .artifacts import HTML, INVENTORY, NOTEBOOK, QUARTO_CONFIG, SOURCE, STATIC
from .inspection import (
    DEFAULT_INSPECTION_HTML,
    build_inspection_record,
    render_inspection_html,
)
from .inventory import InventoryError, build_inventory, load_inventory, sha256, static_inventory

REPORT_SOURCE = """# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
#

# %%
"""

QUARTO_SOURCE = """project:
  type: default

execute:
  enabled: false

format:
  html:
    embed-resources: false
    toc: true
    code-fold: true
"""

PROJECT_SOURCE = """[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "ipykernel>=7,<8",
  "jupytext>=1.19,<2",
  "nbconvert>=7.17,<8",
]
"""


class ReportError(RuntimeError):
    """One user-actionable report operation failure."""


def project_root(value: str | Path) -> Path:
    if isinstance(value, str) and not value:
        raise ReportError("report project root cannot be empty")
    return Path(value).expanduser().resolve()


def run_command(command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReportError(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result


def normalized_project_name(root: Path) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", root.name.lower()).strip("-")
    return name or "executable-report"


def command_new(args: argparse.Namespace) -> int:
    root = project_root(args.root)
    if root.exists() and not root.is_dir():
        raise ReportError(f"report project root is not a directory: {root}")
    if root.is_dir():
        existing = sorted(path.name for path in root.iterdir())
        if existing:
            names = ", ".join(existing[:5])
            suffix = ", ..." if len(existing) > 5 else ""
            raise ReportError(f"report new requires an empty project root; found: {names}{suffix}")
    else:
        root.mkdir(parents=True)
    files = {
        root / "pyproject.toml": PROJECT_SOURCE.format(name=normalized_project_name(root)),
        root / SOURCE: REPORT_SOURCE,
        root / QUARTO_CONFIG: QUARTO_SOURCE,
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
    print(f"Created report project: {root}")
    for path in files:
        print(f"  input  {path.name}")
    return 0


def execution_prefix(args: argparse.Namespace, root: Path) -> list[str]:
    if args.uv:
        uv = shutil.which("uv")
        if not uv:
            raise ReportError("uv was requested but is not installed")
        return [uv, "run", "--project", str(root), "python"]
    python = Path(args.python).expanduser()
    if not python.is_absolute():
        python = Path.cwd() / python
    python = python.absolute()
    if not python.is_file():
        raise ReportError(f"Python interpreter does not exist: {python}")
    return [str(python)]


def command_run(args: argparse.Namespace) -> int:
    root = project_root(args.root)
    source = root / SOURCE
    if not source.is_file():
        raise ReportError(f"missing report source: {source}")
    prefix = execution_prefix(args, root)
    temporary_input = root / ".report.unexecuted.ipynb"
    temporary_output = root / ".report.executed.next.ipynb"
    source_hash = sha256(source)
    for path in (temporary_input, temporary_output):
        path.unlink(missing_ok=True)

    try:
        run_command(
            [*prefix, "-m", "jupytext", "--to", "ipynb", SOURCE, "--output", temporary_input.name],
            cwd=root,
        )
        run_command(
            [
                *prefix,
                "-m",
                "nbconvert",
                "--to",
                "notebook",
                "--execute",
                temporary_input.name,
                "--output",
                temporary_output.name,
                f"--ExecutePreprocessor.timeout={args.timeout}",
            ],
            cwd=root,
        )
        if sha256(source) != source_hash:
            raise ReportError("report.py changed during execution; the output was not promoted")
        runtime = run_command(
            [
                *prefix,
                "-c",
                "import json,platform,sys; print(json.dumps({'executable':sys.executable,'python':platform.python_version()}))",
            ],
            cwd=root,
        )
        notebook = json.loads(temporary_output.read_text(encoding="utf-8"))
        notebook.setdefault("metadata", {})["executable_report"] = {
            "source": SOURCE,
            "source_sha256": source_hash,
            "executed_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
            "environment": "project_uv" if args.uv else "external_python",
            **json.loads(runtime.stdout.strip()),
        }
        temporary_output.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
        os.replace(temporary_output, root / NOTEBOOK)
    finally:
        temporary_input.unlink(missing_ok=True)
        temporary_output.unlink(missing_ok=True)

    print(f"Executed {SOURCE} -> {NOTEBOOK}")
    if args.uv:
        print("Environment: project uv")
    else:
        python = Path(args.python).expanduser()
        if not python.is_absolute():
            python = Path.cwd() / python
        print(f"Environment: {python.absolute()}")
    return 0


def _quarto_version_key(path: Path) -> tuple[int, tuple[int, ...], str]:
    version = path.parent.parent.name
    if re.fullmatch(r"\d+(?:\.\d+)*", version):
        return (1, tuple(int(part) for part in version.split(".")), version)
    return (0, (), version)


def locate_quarto(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.is_file():
            return path
        raise ReportError(f"Quarto executable does not exist: {path}")
    found = shutil.which("quarto")
    if found:
        return Path(found).resolve()
    candidates = [
        path for path in Path.home().glob(".local/quarto/*/bin/quarto") if path.is_file()
    ]
    if candidates:
        return max(candidates, key=_quarto_version_key)
    raise ReportError("Quarto was not found on PATH or under ~/.local/quarto/*/bin/quarto")


def verify_quarto_config(root: Path) -> None:
    config = root / QUARTO_CONFIG
    if not config.is_file():
        raise ReportError(f"missing Quarto policy: {config}")


def _rewrite_resource_attributes(html: str, old: str, new: str) -> str:
    pattern = re.compile(
        r"(?P<prefix>\b(?:src|href)\s*=\s*[\"'])(?P<relative>\./)?"
        + re.escape(old)
        + r"/",
        re.IGNORECASE,
    )
    return pattern.sub(
        lambda match: f"{match.group('prefix')}{match.group('relative') or ''}{new}/",
        html,
    )


def promote_static_resources(root: Path, temporary_html: Path) -> None:
    target = root / STATIC
    candidates = [
        root / f"{Path(NOTEBOOK).stem}_files",
        root / f"{temporary_html.stem}_files",
        root / "site_libs",
    ]
    existing = [path for path in candidates if path.is_dir()]
    if target.exists():
        shutil.rmtree(target)
    if not existing:
        return
    primary = existing[0]
    primary.rename(target)
    html = temporary_html.read_text(encoding="utf-8")
    html = _rewrite_resource_attributes(html, primary.name, STATIC)
    for extra in existing[1:]:
        destination = target / extra.name
        extra.rename(destination)
        html = _rewrite_resource_attributes(html, extra.name, f"{STATIC}/{extra.name}")
    temporary_html.write_text(html, encoding="utf-8")


def command_render(args: argparse.Namespace) -> int:
    root = project_root(args.root)
    notebook = root / NOTEBOOK
    if not notebook.is_file():
        raise ReportError(f"missing executed notebook: {notebook}")
    verify_quarto_config(root)
    quarto = locate_quarto(args.quarto)
    version = run_command([str(quarto), "--version"], cwd=root).stdout.strip()
    notebook_hash = sha256(notebook)
    temporary_html = root / "report.rendered.next.html"
    temporary_html.unlink(missing_ok=True)
    for candidate in (
        root / f"{Path(NOTEBOOK).stem}_files",
        root / "report.rendered.next_files",
        root / "site_libs",
    ):
        if candidate.is_dir():
            shutil.rmtree(candidate)

    run_command(
        [
            str(quarto),
            "render",
            NOTEBOOK,
            "--to",
            "html",
            "--no-execute",
            "--output",
            temporary_html.name,
        ],
        cwd=root,
    )
    if sha256(notebook) != notebook_hash:
        temporary_html.unlink(missing_ok=True)
        raise ReportError("Quarto changed the executed notebook; rendered output was rejected")
    if not temporary_html.is_file():
        raise ReportError(f"Quarto did not create {temporary_html.name}")

    promote_static_resources(root, temporary_html)
    os.replace(temporary_html, root / HTML)
    inventory = build_inventory(root, quarto_version=version)
    (root / INVENTORY).write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {NOTEBOOK} -> {HTML}")
    print(f"Static resources: {STATIC}/ ({len(inventory['static']['files'])} files)")
    print(f"Inventory: {INVENTORY}")
    print(f"Status: {inventory['status']}")
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    root = project_root(args.root)
    inventory_path = root / INVENTORY
    if not inventory_path.is_file():
        raise ReportError(f"missing report inventory: {inventory_path}; run report render first")
    try:
        inventory = load_inventory(inventory_path)
    except InventoryError as error:
        raise ReportError(f"invalid report inventory: {error}") from error
    problems: list[str] = []
    notebook = inventory["notebook"]
    if notebook["error_outputs"]:
        problems.append(f"executed notebook contains {notebook['error_outputs']} error outputs")
    if notebook["unexecuted_code_cells"]:
        problems.append(
            f"executed notebook contains {notebook['unexecuted_code_cells']} unexecuted code cells"
        )
    for key, expected_name in (("source", SOURCE), ("notebook", NOTEBOOK), ("html", HTML)):
        path = root / expected_name
        if not path.is_file():
            problems.append(f"missing {expected_name}")
        elif sha256(path) != inventory[key]["sha256"]:
            problems.append(f"{expected_name} changed after inventory")
    execution = inventory["notebook"].get("execution", {})
    source_path = root / SOURCE
    if source_path.is_file() and execution.get("source_sha256") != sha256(source_path):
        problems.append("executed notebook is stale relative to report.py")

    recorded_static = {item["path"]: item["sha256"] for item in inventory["static"]["files"]}
    current_static = {item["path"]: item["sha256"] for item in static_inventory(root)}
    for path in sorted(recorded_static.keys() | current_static.keys()):
        if path not in current_static:
            problems.append(f"missing {path}")
        elif path not in recorded_static:
            problems.append(f"unexpected static file {path}")
        elif current_static[path] != recorded_static[path]:
            problems.append(f"{path} changed after inventory")

    rendered_path: str | None = None
    output_path: Path | None = None
    if args.render is not None:
        relative = Path(args.render)
        if relative.is_absolute() or ".." in relative.parts:
            raise ReportError("inspection render path must stay inside the report project")
        output_path = root / relative
        rendered_path = relative.as_posix()

    result = build_inspection_record(
        inventory,
        problems,
        rendered_path=rendered_path,
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_inspection_html(result), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if problems else 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="report", description="Executable report vertical slice")
    subcommands = result.add_subparsers(dest="command", required=True)

    new = subcommands.add_parser("new", help="create a flat report project")
    new.add_argument("root", nargs="?", default=".")
    new.set_defaults(handler=command_new)

    run = subcommands.add_parser("run", help="execute report.py into report.executed.ipynb")
    run.add_argument("root", nargs="?", default=".")
    environment = run.add_mutually_exclusive_group(required=True)
    environment.add_argument("--python", help="explicit Python interpreter path")
    environment.add_argument("--uv", action="store_true", help="use the report project's uv environment")
    run.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="per-cell execution timeout in seconds",
    )
    run.set_defaults(handler=command_run)

    render = subcommands.add_parser("render", help="render saved notebook outputs with Quarto")
    render.add_argument("root", nargs="?", default=".")
    render.add_argument("--quarto", help="explicit Quarto executable path")
    render.set_defaults(handler=command_render)

    inspect = subcommands.add_parser("inspect", help="inspect this system's generated report artifacts")
    inspect.add_argument("root", nargs="?", default=".")
    inspect.add_argument(
        "--render",
        nargs="?",
        const=DEFAULT_INSPECTION_HTML,
        metavar="PATH",
        help=f"write a human HTML projection (default: {DEFAULT_INSPECTION_HTML})",
    )
    inspect.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    inspect.set_defaults(handler=command_inspect)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except ReportError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
