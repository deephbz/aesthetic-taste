"""JSON-first inspection records and their human HTML projection."""

from __future__ import annotations

import html
import json
from typing import Any

INSPECTION_KIND = "executable_report_inspection"
INSPECTION_SCHEMA_VERSION = "0.1.0"
DEFAULT_INSPECTION_HTML = "report.inspect.html"


def byte_label(value: int) -> str:
    if value < 1024:
        return f"{value:,} B"
    if value < 1024**2:
        return f"{value / 1024:.1f} KiB"
    return f"{value / 1024**2:.2f} MiB"


def build_inspection_record(
    inventory: dict[str, Any],
    problems: list[str],
    *,
    rendered_path: str | None = None,
) -> dict[str, Any]:
    """Build one machine authority from an accepted inventory and drift checks."""

    notebook = inventory["notebook"]
    html_record = inventory["html"]
    static = inventory["static"]
    artifact_bytes = (
        inventory["source"]["bytes"]
        + notebook["bytes"]
        + html_record["bytes"]
        + static["bytes"]
    )
    size_tree = {
        "label": "report artifacts",
        "unit": "serialized_bytes",
        "bytes": artifact_bytes,
        "children_relationship": "additive",
        "children": [
            {
                "label": inventory["source"]["path"],
                "kind": "canonical_source",
                "bytes": inventory["source"]["bytes"],
            },
            {
                "label": notebook["path"],
                "kind": "executed_notebook",
                "bytes": notebook["bytes"],
                "children_relationship": "contained_not_additive",
                "children": [
                    {
                        "label": "serialized cell outputs",
                        "kind": "notebook_output_subset",
                        "bytes": notebook["output_bytes"],
                    }
                ],
            },
            {
                "label": html_record["path"],
                "kind": "rendered_html",
                "bytes": html_record["bytes"],
            },
            {
                "label": static["path"],
                "kind": "static_resources",
                "bytes": static["bytes"],
                "children_relationship": "additive",
                "children": [
                    {
                        "label": item["path"],
                        "kind": "static_resource",
                        "bytes": item["bytes"],
                    }
                    for item in static["files"]
                ],
            },
        ],
    }
    return {
        "schema_version": INSPECTION_SCHEMA_VERSION,
        "kind": INSPECTION_KIND,
        "status": "warning" if problems else "passed",
        "problems": problems,
        "inventory": inventory,
        "views": {
            "size_tree": size_tree,
            "dimensions": {
                "serialized_bytes": {
                    "artifact_total": artifact_bytes,
                    "notebook_outputs": notebook["output_bytes"],
                    "static_resources": static["bytes"],
                },
                "html_structure": {
                    "elements": html_record["elements"],
                    "tag_counts": html_record["tag_counts"],
                    "headings": len(html_record["headings"]),
                    "section_elements": html_record["section_elements"],
                },
                "execution": {
                    "code_cells": notebook["code_cells"],
                    "executed_code_cells": notebook["executed_code_cells"],
                    "unexecuted_code_cells": notebook["unexecuted_code_cells"],
                    "error_outputs": notebook["error_outputs"],
                },
            },
            "section_output_bytes": notebook["section_output_bytes"],
        },
        "human_projection": {"path": rendered_path} if rendered_path else None,
        "limitations": [
            "Serialized bytes, parsed element counts, and execution counts are separate dimensions.",
            "Parsed HTML structure does not measure browser heap, layout, paint, or interaction latency.",
            "HTML section element counts include nested descendants, so nested section rows are not additive.",
            "Contained byte nodes describe subsets and must not be added to their parent again.",
        ],
    }


def _tree_html(node: dict[str, Any], root_bytes: int) -> str:
    value = int(node.get("bytes", 0))
    width = 0 if not root_bytes else max(0.5, 100 * value / root_bytes)
    relationship = node.get("children_relationship")
    relationship_html = (
        f"<small>{html.escape(str(relationship).replace('_', ' '))}</small>"
        if relationship
        else ""
    )
    children = node.get("children", [])
    nested = (
        "<ul>" + "".join(_tree_html(child, root_bytes) for child in children) + "</ul>"
        if children
        else ""
    )
    return (
        "<li><div class='tree-line'><span>"
        + html.escape(str(node["label"]))
        + "</span><strong>"
        + byte_label(value)
        + "</strong></div>"
        + relationship_html
        + f"<div class='bar'><i style='width:{width:.3f}%'></i></div>"
        + nested
        + "</li>"
    )


def _rows_html(rows: list[tuple[str, str]]) -> str:
    return "".join(
        "<tr><td>" + html.escape(label) + "</td><td>" + html.escape(value) + "</td></tr>"
        for label, value in rows
    )


def render_inspection_html(record: dict[str, Any]) -> str:
    """Render a self-contained human projection from one inspection record."""

    inventory = record["inventory"]
    dimensions = record["views"]["dimensions"]
    size_tree = record["views"]["size_tree"]
    section_rows = [
        (section, byte_label(value))
        for section, value in sorted(
            record["views"]["section_output_bytes"].items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]
    html_section_rows = [
        (
            str(item.get("title") or item["id"]),
            f"{item['elements']:,}",
        )
        for item in sorted(
            dimensions["html_structure"]["section_elements"],
            key=lambda item: item["elements"],
            reverse=True,
        )[:20]
    ]
    tag_rows = [
        (tag, f"{count:,}")
        for tag, count in sorted(
            inventory["html"]["tag_counts"].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20]
    ]
    problems = record["problems"]
    problems_html = (
        "<ul class='problems'>"
        + "".join(f"<li>{html.escape(problem)}</li>" for problem in problems)
        + "</ul>"
        if problems
        else "<p class='passed'>No artifact drift or execution problem was found.</p>"
    )
    embedded = (
        json.dumps(record, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><link rel="icon" href="data:,">
<title>Executable report inspection</title><style>
:root{{--ink:#172126;--muted:#5e6b70;--paper:#fffdf8;--line:#d9d3c6;--accent:#2764ae}}
*{{box-sizing:border-box}}body{{margin:0;background:#f3f0e9;color:var(--ink);font:14px/1.45 system-ui,sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:28px}}h1{{margin:0}}h2{{margin-top:28px}}
.lede{{color:var(--muted);max-width:78ch}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.card,.panel{{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:14px}}
.card strong{{display:block;color:#0f5f73;font-size:21px}}.card small{{color:var(--muted)}}
.tree ul{{list-style:none;margin:8px 0 0 12px;padding-left:20px;border-left:1px solid var(--line)}}
.tree>ul{{margin-left:0;padding-left:0;border:0}}.tree li{{margin:8px 0}}.tree-line{{display:flex;gap:16px;justify-content:space-between}}
.tree small{{display:block;color:var(--muted)}}.bar{{height:5px;background:#ebe6dc;border-radius:4px;overflow:hidden}}
.bar i{{display:block;height:100%;background:var(--accent)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left}}
th{{background:var(--ink);color:white}}.passed{{border-left:4px solid #23845b;padding-left:10px}}
.problems{{border-left:4px solid #b8423e}}code{{font-size:12px}}@media(max-width:800px){{.cards,.grid{{grid-template-columns:1fr 1fr}}}}
</style></head><body><main>
<h1>Executable report inspection</h1>
<p class="lede">One JSON inspection record is the authority. This page is its derived human projection.
Serialized bytes and parsed DOM elements are separate dimensions.</p>
<section class="cards">
  <div class="card"><strong>{byte_label(dimensions['serialized_bytes']['artifact_total'])}</strong><small>serialized report artifacts</small></div>
  <div class="card"><strong>{inventory['html']['elements']:,}</strong><small>parsed HTML elements</small></div>
  <div class="card"><strong>{inventory['notebook']['executed_code_cells']}/{inventory['notebook']['code_cells']}</strong><small>executed code cells</small></div>
  <div class="card"><strong>{len(inventory['static']['files']):,}</strong><small>static resource files</small></div>
</section>
<h2>Artifact size tree</h2><section class="panel tree"><ul>{_tree_html(size_tree, size_tree['bytes'])}</ul></section>
<h2>Structure and output concentration</h2><section class="grid">
  <div class="panel"><h3>Parsed HTML elements by section</h3><p class="lede">Counts include nested descendants.</p><table><thead><tr><th>section</th><th>elements</th></tr></thead><tbody>{_rows_html(html_section_rows)}</tbody></table></div>
  <div class="panel"><h3>Largest HTML tag groups</h3><table><thead><tr><th>tag</th><th>elements</th></tr></thead><tbody>{_rows_html(tag_rows)}</tbody></table></div>
  <div class="panel"><h3>Notebook output bytes by section</h3><table><thead><tr><th>section</th><th>bytes</th></tr></thead><tbody>{_rows_html(section_rows)}</tbody></table></div>
</section>
<h2>Inspection status</h2><section class="panel">{problems_html}</section>
<h2>Interpretation boundary</h2><section class="panel"><ul>
  {''.join(f'<li>{html.escape(item)}</li>' for item in record['limitations'])}
</ul></section>
<script type="application/json" id="inspection-record">{embedded}</script>
</main></body></html>"""
