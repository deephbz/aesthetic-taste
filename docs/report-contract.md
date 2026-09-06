---
purpose: Define what a published report is from the outside. The report and
  its notebook are a black box here.
owns: Deployment shape (static bundle, no application server), data and
  view-state authority, notebook-to-web parity, durability levels, browser
  performance stance.
does-not-own: Report code structure and live authoring (report-authoring skill),
  artifact names and build behavior (report-cli-design.md), or technology advice.
stage: consolidation. The contract is stable in practice; wording still changes.
status: active
---

# Report contract

These rules define the report contract: what a published report is, where its
data and state live, and what stays true across JupyterLab and the rendered
static bundle. They treat the report as a black box. [Report
authoring](../.agents/skills/report-authoring/SKILL.md) looks inside it.

## Scope

- **Immutable, read-only data boundary.** Treat upstream data production as an
  external black box that publishes immutable data artifacts; reports consume
  and transform them without writing back.
- **Static-bundle deployment.** Prefer self-contained static artifacts or
  bundles (html + js + wasm + data files) that can be stored, served, copied,
  and reopened without an application service.
- **No application server by default.** Use static file transport. Server-side
  compute, databases, authentication, and persistent server-side application
  state are not required unless the user and the workload explicitly require
  them.
- **Browser-first execution.** Keep latency-sensitive interaction and
  analytical work close to the browser when practical; move computation
  elsewhere only when workload constraints justify it.

## Data, state, and compute

- **Report data boundary.** Separate large upstream data from report-resident
  data; materialize only the bounded data required for report consumption and
  browser-side exploration, and keep expensive or large-scale transformations
  upstream.
- **Explicit, reproducible transformation.** Model analytical results as
  reproducible transformations of explicit inputs where practical, and keep
  external effects and environment-dependent behavior at clear system
  boundaries.
- **Reconstructible derived state.** Treat caches and materialized computation
  as non-authoritative accelerators that may be discarded and rebuilt from
  durable inputs. Choose caching, identity, and invalidation mechanisms
  according to the workload; do not engineer them ahead of need.
- **Portable semantic view state.** Keep shareable view state independent of
  renderer-specific state. Allow selected valid state to be serialized into
  portable representations such as the URL. Keep renderer adapters and
  transient interaction state non-authoritative.

```text
DATA / COMPUTE                          VIEW

durable immutable inputs              portable view state
        ↓                                     ↓
reproducible transformation           transient interaction
        ↓                                     ↓
reconstructible materialization ──→   rendered view
```

## Visual

- **Notebook-to-web semantic parity.** Preserve the same report data,
  visualization, interaction, and view-state semantics across JupyterLab and
  Quarto-rendered HTML, and allow environment-specific adapters.

```text
Shared across environments
├── charts and tables
├── filters and groupings
├── selections
├── linked-view behavior
├── view-state model
└── interaction semantics

Environment-specific
├── Jupyter display integration
├── Quarto embedding
├── URL ↔ view-state synchronization
└── other host-specific lifecycle concerns
```

- **Reading orientation.** Long narrative reports must make their sections easy
  to find. Current-section indicators must follow scrolling and layout changes.
  Page navigation is a host-specific concern; analytical views keep the same
  meaning across notebook and HTML hosts.
- **Supported hosts.** Verify rendered output in JupyterLab/notebooks and in
  an HTML bundle served by an HTTP server. Analytical meaning must agree in
  both hosts; navigation and other host controls can differ.

Presentation defaults and display-format choices live in the
[presentation guide](../.agents/skills/report-presentation/SKILL.md), not in this contract.

- **Recoverable, durable reporting.** Interactive rendering is not the sole
  source of analytical meaning. Level 1 is the default: the `report` CLI
  records source, environment, and artifact provenance on every run, so every
  report is reconstructible. Levels 2 and 3 are opt-in. Add them only when the
  user asks for them.

```text
Level 1 — Reconstructible (default)
immutable data + source + provenance
        ↓
can regenerate

Level 2 — Cheap automatic fallback (on request)
generated static snapshot/table
        ↓
readable without rich runtime

Level 3 — Fully archival artifact (on request)
self-contained, frozen dependencies,
multiple representations
```

## Performance

- **Efficient analytical data representation.** Prefer compact, columnar, and
  zero- or low-copy data representations for large analytical workloads; use
  row-oriented or textual formats when their simplicity is more valuable than
  throughput.
- **Working-set proportionality.** Keep latency-sensitive browser computation,
  transfer, and rendering proportional to the current analytical view rather
  than the full available dataset; perform reduction at the most appropriate
  layer for the workload.

For current architecture advice, read
[technology choices](../.agents/skills/report-authoring/references/technology-choices.md).
That dated guidance can change independently of this contract.
