---
name: report-reading
description: Read, inspect, or diagnose an existing executed report without rerunning its analysis. Use to learn what a report found, to read its outputs as an agent within a small context budget, to check saved artifacts for drift, or to investigate a recorded verification failure.
---

# Report reading

Own reading an existing report: its agent view, artifact inspection, and
receipt-driven diagnosis. [report-delivery](../report-delivery/SKILL.md) owns
building, verifying, and serving.
Stage: exploration for the agent view; sharing for inspection.

Run the CLI from the repository root with
`uv run --project components/reporting --no-config report ...`.

```text
report.executed.ipynb (the record)
├── human view:  report.rendered.html     rich forms only
└── agent view:  report agent-view ROOT   prose + compact forms, by cell ID
```

## Read what a report says

1. Run `report agent-view ROOT`. It prints the markdown prose whole and each
   output's compact form under `[cell-id#n]`. Add `--code` for code sources,
   `--notebook PATH` for another saved notebook, `--limit` to change the bound.
2. Cite outputs by cell ID; output positions are not stable. A notebook keeps
   its cell IDs across re-execution. A Python source keeps an ID only when the
   cell is marked `# %% id="outcomes"`; `report run` makes the marker the
   native ID. Unmarked cells get a fresh ID on each build.
3. Treat `[...; no compact form]` as missing facts, not empty output. Open the
   cell in the HTML report, or give the producer a `text/plain` form;
   `Mermaid(source, text=...)` takes a summary.
4. Reread data or recompute through the report's cached steps when a compact
   form is too small for the question. Do not parse the rendered HTML.

## Check saved artifacts

1. Start with `report inspect ROOT` to check saved artifacts and drift without
   rerunning the analysis. Preserve existing failure evidence while diagnosing.
2. Read an existing `report.verify.json` when investigating its reported failure.
   Run `report verify ROOT` when current browser evidence is needed.
3. Rebuild through report-delivery when source changes or stale artifacts
   require it.

When the input is a live notebook, `report notebook status` and `read` establish
the current server, kernel, cell source, and output state.

## Investigate browser failures

Start from `report.verify.json`, not from a new browser harness. Read the first
problem and run its `diagnostics.quick_start` call from the report root. Use the
problem selector, when present, for a targeted screenshot and DOM/layout
extraction; add a trace only when the generic receipt is insufficient.

For library-specific inspection, use `browser_session()` and query the
renderer-owned public API, such as a Bokeh model, Perspective saved state, or AG
Grid API. Keep semantic acceptance checks in `window.__REPORT_VERIFY__` rather
than coupling the generic verifier to private renderer internals.

## Completion

Report what you read with cell-ID pointers, the checks performed, and any output
whose facts you could not read in compact form.
