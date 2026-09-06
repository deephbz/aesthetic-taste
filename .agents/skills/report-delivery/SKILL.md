---
name: report-delivery
description: Build and check saved report outputs, or inspect and diagnose an existing report without rerunning analysis. Use for the report CLI, HTTP serving, browser receipts, and host verification.
---

# Report delivery

Own producing and checking saved report outputs, static serving practice, and
receipt-driven diagnosis. Live kernel work belongs to
[report-authoring](../report-authoring/SKILL.md). Deployment infrastructure remains
outside this workflow.
Stage: sharing for the CLI workflow; receipt and diagnostic schemas remain pre-1.0.

Read the [report contract](../../../docs/report-contract.md) for the required
outcomes. Read [CLI design](../../../docs/report-cli-design.md) for artifact names,
command behavior, receipt semantics, failure rules, and evidence limits.
Use [report-presentation](../report-presentation/SKILL.md) when a repair changes
navigation or display integration.

## Run the local reporting tools

Use the cloned repository as described in [the repository guide](../../../README.md#use-reporting-tools).
From its root, prefix CLI examples with `uv run --project components/reporting --no-config`.
The `report` command below refers to that component.

## Produce a report

1. For a new report, use `report new ROOT` in a missing or empty directory.
   Use the authoring skill to create or revise its analysis.
2. Before release, run one clean `report run`, `report render`, `report inspect`,
   and `report verify`, in that order. Choose the report's execution environment
   as described in the CLI reference.
3. Read the inspection and verification results. Investigate failed checks using
   the procedure below, and check the requested hosts and outputs.

## Check an existing report

1. Start with `report inspect ROOT` to check saved artifacts and drift without
   rerunning the analysis. Preserve the existing failure evidence while diagnosing.
2. Read an existing `report.verify.json` when investigating its reported failure.
   Run `report verify ROOT` when current browser evidence is needed.
3. Use the diagnostics below to isolate failures. Rebuild when source changes or
   stale artifacts require it; verification can run independently of a build.

## Verify hosts and outputs

The CLI browser check covers the served HTML; it does not establish notebook
parity or analytical correctness. Inspect actual JupyterLab/notebook output and
HTTP-served HTML for the same analytical meaning, controls, and view state.
Read screenshots when pixels matter. Check requested print or spreadsheet
outputs separately in their target representation. For tables, use
[table-presentation](../table-presentation/SKILL.md#reproduce-and-verify-the-result)
for value checks and table-specific layout concerns.

## Serve the static report

Serve the report root through HTTP. Do not open fetch-based reports with a
`file:` URL. Enable Brotli compression and keep gzip as fallback. Prefer HTTP/2
or HTTP/3 when the host supports it. Use system fonts to avoid webfont requests.
Set long immutable cache headers only for content-hashed resources.

## Investigate browser failures

Start from `report.verify.json`, not from a new browser harness. Read the first
problem and run its `diagnostics.quick_start` call from the report root. Use the
problem selector, when present, for a targeted screenshot and DOM/layout extraction; add a
trace only when the generic receipt is insufficient.

For library-specific inspection, use `browser_session()` and query the
renderer-owned public API, such as a Bokeh model, Perspective saved state, or AG
Grid API. Keep semantic acceptance checks in `window.__REPORT_VERIFY__` rather
than coupling the generic verifier to private renderer internals.

## Completion

Report the artifact location, checks performed, evidence receipts, and remaining
failures or unverified outputs. A partial check supports only its stated scope;
build completion alone does not establish release readiness. Reuse unchanged
verification evidence when it still covers the relevant source, tools, and hosts.
