"""Agent view: a compact text projection of one executed notebook.

The executed notebook is the record. The rendered HTML is the human view; this
module derives the agent view from the same record. It keeps prose whole,
reads each output's compact form (``text/plain``, else ``text/markdown``), and
names each output by its stable cell ID. An output with only a rich form
appears as a one-line stub, which shows the producer lacks a compact form.
"""
from __future__ import annotations

import json

COMPACT = ("text/plain", "text/markdown")
DEFAULT_LIMIT = 1500  # characters per output


def _text(value) -> str:
    return "".join(value) if isinstance(value, list) else value if isinstance(value, str) else json.dumps(value)


def _bounded(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n… [cut at {limit} of {len(text)} characters]"


def _output(output: dict, limit: int) -> tuple[str, str, int]:
    """Return a header, the compact text, and the bytes the output stores."""
    kind = output.get("output_type")
    if kind == "stream":
        text = _text(output.get("text", ""))
        return output.get("name", "stream"), _bounded(text.rstrip("\n"), limit), len(text.encode())
    if kind == "error":
        text = f"{output.get('ename')}: {output.get('evalue')}"
        return "error", _bounded(text, limit), len(json.dumps(output).encode())
    data = output.get("data", {})
    stored = sum(len(_text(value).encode()) for value in data.values())
    form = next((mime for mime in COMPACT if mime in data), None)
    text = _bounded(_text(data[form]).rstrip("\n"), limit) if form else f"[{', '.join(data)}; no compact form]"
    return ", ".join(data), text, stored


def agent_view(notebook: dict, *, code: bool = False, limit: int = DEFAULT_LIMIT) -> str:
    """Return the agent view of an executed notebook as plain text."""
    lines: list[str] = []
    stored_total = 0
    for cell in notebook.get("cells", []):
        source = _text(cell.get("source", "")).rstrip("\n")
        if cell.get("cell_type") == "markdown":
            lines += [source, ""]
            continue
        if cell.get("cell_type") != "code":
            continue
        cell_id = cell.get("id", "?")
        if code and source:
            lines.append(f"[{cell_id}] code")
            lines += ["    " + line for line in source.splitlines()]
        for number, output in enumerate(cell.get("outputs", [])):
            header, text, stored = _output(output, limit)
            stored_total += stored
            lines.append(f"[{cell_id}#{number}] {header} · {stored:,} B stored")
            lines += ["    " + line for line in text.splitlines()]
        if code and source or cell.get("outputs"):
            lines.append("")
    body = "\n".join(lines).rstrip("\n")
    return f"{body}\n\n[agent view: {len(body.encode()):,} B; outputs store {stored_total:,} B]\n"
