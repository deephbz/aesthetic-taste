---
name: executable-report-collaboration
description: Use for fast human-agent authoring and efficient static report serving.
---

# Executable report collaboration

Read `principles.md` for the report contract. Read `report-cli-design.md` for
artifact names, commands, and failure rules. This guide adds only the live
authoring and serving procedure.

## Iterate in a live kernel

1. Keep one Jupyter kernel active during research.
2. Rerun only the changed cells or sections.
3. Use `%autoreload 3` when reusable local modules change.
4. If available, use Jupyter MCP for cell-aware kernel operations.
5. Before release, run one clean `report run`, `report render`, and `report inspect`.

## Coordinate human and agent edits

Use Jupytext `.py` as the editable source. Let agents edit this file through
normal version-control tools. Enable `jupyter-collaboration` so external file
changes update JupyterLab's live document model. For simultaneous edits to one
cell, use a shared-document or cell-aware API and address stable cell IDs.

## Serve the static report

Serve the report root through HTTP. Do not open fetch-based reports with a
`file:` URL. Enable Brotli compression and keep gzip as fallback. Prefer HTTP/2
or HTTP/3 when the host supports it. Use system fonts to avoid webfont requests.
Set long immutable cache headers only for content-hashed resources.
