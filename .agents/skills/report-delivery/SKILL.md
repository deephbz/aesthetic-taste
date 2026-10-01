---
name: report-delivery
description: Build, verify, and serve saved report outputs. Use for the report CLI build sequence, HTTP serving, browser verification receipts, and host checks.
---

# Report delivery

Own producing and verifying saved report outputs and static serving practice.
Reading, inspecting, or diagnosing an existing report belongs to
[report-reading](../report-reading/SKILL.md). Live kernel work belongs to
[report-authoring](../report-authoring/SKILL.md) and the
[notebook collaboration guide](../../../docs/notebook-collaboration.md).
Deployment infrastructure remains outside this workflow.
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
   For an existing study, use `report new ROOT --adopt`. It adds only the
   missing inputs and keeps every existing file, including `pyproject.toml`;
   add the report dependencies to a kept project yourself. Use the authoring
   skill to create or revise its analysis.
2. If the report was authored in a live notebook, review the live source and
   outputs, then use `report notebook export` to create the one-way Jupytext
   projection. Treat that export as the source snapshot for the clean build.
3. Before release, run one clean `report run`, `report render`, `report inspect`,
   and `report verify`, in that order. Choose the report's execution environment
   as described in the CLI reference. Pass a native notebook with
   `report run --source`; preserve the same source-hash and promotion
   guarantees.
4. Read the inspection and verification results. Investigate failed checks with
   [report-reading](../report-reading/SKILL.md#investigate-browser-failures), and
   check the requested hosts and outputs.
5. Run `report agent-view` and check which outputs lack a compact form.

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

## Completion

Report the artifact location, checks performed, evidence receipts, and remaining
failures or unverified outputs. A partial check supports only its stated scope;
build completion alone does not establish release readiness. Reuse unchanged
verification evidence when it still covers the relevant source, tools, and hosts.
For a live notebook handoff, include the exported source snapshot and note any
same-cell conflict, stale source/output, kernel-state, trust, or renderer limits.
