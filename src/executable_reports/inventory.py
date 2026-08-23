"""Shared semantic inventory for executable-report render and inspection."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .artifacts import HTML, NOTEBOOK, SOURCE, STATIC

SCHEMA_VERSION = "0.2.0"
INVENTORY_KIND = "executable_report_inventory"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def joined(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return "" if value is None else str(value)


class InventoryError(ValueError):
    """An input is not a supported executable-report inventory."""


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InventoryError(f"inventory field {field!r} must be an object")
    return value


def _required(value: dict[str, Any], field: str, expected_type: type) -> Any:
    if field not in value or type(value[field]) is not expected_type:
        raise InventoryError(f"inventory field {field!r} has an invalid type")
    return value[field]


def load_inventory(path: Path) -> dict[str, Any]:
    """Load and validate the inventory fields used by report inspection."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InventoryError(f"cannot read inventory: {error}") from error
    inventory = _mapping(value, "root")
    if inventory.get("kind") != INVENTORY_KIND:
        raise InventoryError(f"inventory kind must be {INVENTORY_KIND!r}")
    if inventory.get("schema_version") != SCHEMA_VERSION:
        raise InventoryError(f"inventory schema must be {SCHEMA_VERSION}")
    if _required(inventory, "status", str) not in {"passed", "warning"}:
        raise InventoryError("inventory status must be 'passed' or 'warning'")

    source = _mapping(inventory.get("source"), "source")
    notebook = _mapping(inventory.get("notebook"), "notebook")
    html = _mapping(inventory.get("html"), "html")
    static = _mapping(inventory.get("static"), "static")
    _required(source, "sha256", str)
    for field in ("sha256",):
        _required(notebook, field, str)
        _required(html, field, str)
    counts = {
        field: _required(notebook, field, int)
        for field in (
            "code_cells",
            "executed_code_cells",
            "unexecuted_code_cells",
            "error_outputs",
        )
    }
    if any(value < 0 for value in counts.values()):
        raise InventoryError("inventory notebook counts cannot be negative")
    if counts["executed_code_cells"] + counts["unexecuted_code_cells"] != counts["code_cells"]:
        raise InventoryError("inventory notebook execution counts are inconsistent")
    for field in ("sections", "outputs"):
        _required(notebook, field, list)
    for field in ("mime_counts", "execution"):
        _required(notebook, field, dict)
    _required(notebook, "output_bytes", int)
    section_output_bytes = _required(notebook, "section_output_bytes", dict)
    if any(type(value) is not int or value < 0 for value in section_output_bytes.values()):
        raise InventoryError("inventory section output byte counts are invalid")
    _required(html, "bytes", int)
    _required(html, "elements", int)
    tag_counts = _required(html, "tag_counts", dict)
    if any(type(value) is not int or value < 0 for value in tag_counts.values()):
        raise InventoryError("inventory HTML tag counts are invalid")
    section_elements = _required(html, "section_elements", list)
    for index, item in enumerate(section_elements):
        record = _mapping(item, f"html.section_elements[{index}]")
        _required(record, "id", str)
        _required(record, "elements", int)
    files = _required(static, "files", list)
    _required(static, "bytes", int)
    for index, item in enumerate(files):
        record = _mapping(item, f"static.files[{index}]")
        _required(record, "path", str)
        _required(record, "sha256", str)
    return inventory


class HeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[dict[str, Any]] = []
        self.element_count = 0
        self.tag_counts: Counter[str] = Counter()
        self.section_elements: list[dict[str, Any]] = []
        self._section_stack: list[dict[str, Any]] = []
        self._level: int | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        self.element_count += 1
        self.tag_counts[normalized] += 1
        for section in self._section_stack:
            section["elements"] += 1
        if normalized == "section":
            attributes = dict(attrs)
            record = {
                "id": attributes.get("id") or "(anonymous section)",
                "title": None,
                "elements": 1,
            }
            self.section_elements.append(record)
            self._section_stack.append(record)
        if re.fullmatch(r"h[1-6]", normalized):
            self._level = int(tag[1])
            self._parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        self.element_count += 1
        self.tag_counts[normalized] += 1
        for section in self._section_stack:
            section["elements"] += 1
        if normalized == "section":
            attributes = dict(attrs)
            self.section_elements.append(
                {
                    "id": attributes.get("id") or "(anonymous section)",
                    "title": None,
                    "elements": 1,
                }
            )

    def handle_data(self, data: str) -> None:
        if self._level is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if self._level is not None and normalized == f"h{self._level}":
            title = "".join(self._parts).strip()
            self.headings.append(
                {"level": self._level, "text": title}
            )
            if self._section_stack and not self._section_stack[-1]["title"]:
                self._section_stack[-1]["title"] = title
            self._level = None
            self._parts = []
        if normalized == "section" and self._section_stack:
            self._section_stack.pop()


def notebook_inventory(notebook: dict[str, Any]) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    current_section: str | None = None
    mime_counts: Counter[str] = Counter()
    code_cells = 0
    executed_code_cells = 0
    error_outputs = 0
    output_bytes = 0
    section_output_bytes: Counter[str] = Counter()

    for cell_index, cell in enumerate(notebook.get("cells", []), start=1):
        source = joined(cell.get("source"))
        if cell.get("cell_type") == "markdown":
            for match in HEADING_RE.finditer(source):
                current_section = match.group(2).strip()
                sections.append(
                    {
                        "level": len(match.group(1)),
                        "title": current_section,
                        "cell_index": cell_index,
                    }
                )
        if cell.get("cell_type") != "code" or not source.strip():
            continue
        code_cells += 1
        if cell.get("execution_count") is not None:
            executed_code_cells += 1
        for output_index, output in enumerate(cell.get("outputs", []), start=1):
            data = output.get("data", {})
            mimes = sorted(data) if isinstance(data, dict) else []
            mime_counts.update(mimes)
            if output.get("output_type") == "error":
                error_outputs += 1
            serialized_bytes = len(
                json.dumps(output, ensure_ascii=False, separators=(",", ":")).encode()
            )
            output_bytes += serialized_bytes
            section_output_bytes[current_section or "(unsectioned)"] += serialized_bytes
            outputs.append(
                {
                    "id": f"c{cell_index}-o{output_index}",
                    "cell_index": cell_index,
                    "output_index": output_index,
                    "section": current_section,
                    "output_type": output.get("output_type"),
                    "mimes": mimes,
                    "bytes": serialized_bytes,
                    "error": output.get("ename"),
                }
            )

    return {
        "cells": len(notebook.get("cells", [])),
        "code_cells": code_cells,
        "executed_code_cells": executed_code_cells,
        "unexecuted_code_cells": code_cells - executed_code_cells,
        "error_outputs": error_outputs,
        "mime_counts": dict(sorted(mime_counts.items())),
        "output_bytes": output_bytes,
        "section_output_bytes": dict(sorted(section_output_bytes.items())),
        "sections": sections,
        "outputs": outputs,
        "execution": notebook.get("metadata", {}).get("executable_report", {}),
    }


def static_inventory(root: Path) -> list[dict[str, Any]]:
    static = root / STATIC
    if not static.is_dir():
        return []
    return [
        {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(static.rglob("*"))
        if path.is_file()
    ]


def build_inventory(root: Path, *, quarto_version: str | None = None) -> dict[str, Any]:
    source = root / SOURCE
    notebook_path = root / NOTEBOOK
    html_path = root / HTML
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")
    parser = HeadingParser()
    parser.feed(html)
    notebook_data = notebook_inventory(notebook)
    source_hash = sha256(source)
    recorded_source_hash = notebook_data["execution"].get("source_sha256")

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": INVENTORY_KIND,
        "status": "passed"
        if not notebook_data["error_outputs"]
        and not notebook_data["unexecuted_code_cells"]
        and recorded_source_hash == source_hash
        else "warning",
        "source": {
            "path": SOURCE,
            "bytes": source.stat().st_size,
            "sha256": source_hash,
        },
        "notebook": {
            "path": NOTEBOOK,
            "bytes": notebook_path.stat().st_size,
            "sha256": sha256(notebook_path),
            **notebook_data,
        },
        "html": {
            "path": HTML,
            "bytes": html_path.stat().st_size,
            "sha256": sha256(html_path),
            "headings": parser.headings,
            "elements": parser.element_count,
            "tag_counts": dict(sorted(parser.tag_counts.items())),
            "section_elements": parser.section_elements,
        },
        "static": {
            "path": STATIC,
            "files": (static_files := static_inventory(root)),
            "bytes": sum(item["bytes"] for item in static_files),
        },
        "tools": {"quarto": quarto_version},
        "limitations": [
            "The inventory describes report structure and provenance; it does not prove analytical correctness.",
            "Browser layout and interaction are outside this vertical slice.",
        ],
    }
