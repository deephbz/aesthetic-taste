---
purpose: Define what a published report is from the outside. The report and
  its notebook are a black box here.
owns: Deployment shape (static bundle, no application server), data and
  view-state authority, notebook-to-web parity, durability levels, browser
  performance stance, and the non-normative technology guidance.
does-not-own: Report code structure (report-authoring.md), artifact names and
  build behavior (report-cli-design.md), the live authoring loop (SKILL.md).
stage: consolidation. The contract is stable in practice; wording and the
  technology guidance still change.
status: active
---

# Report contract

These rules define the report contract: what a published report is, where its
data and state live, and what stays true across JupyterLab and the rendered
static bundle. They treat the report as a black box. [Report
authoring](report-authoring.md) looks inside it.

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

## Architecture guidance, 2026 (non-normative)

This section records current technology choices. It is advice, not contract,
and it will change as tools change.

- **Authoring and publication.** Use JupyterLab as the literate research and
  execution environment, and Quarto as the default publication layer for
  static HTML reports. Quarto supports Jupyter-native authoring and
  client-side interactive widgets, and published HTML does not require a
  Python kernel. ([Quarto][1])
- **Data and browser compute.** Prefer Arrow IPC for compact browser-ready
  interchange and Parquet for larger, partitioned, or query-oriented datasets.
  Add DuckDB-Wasm only when browser-side joins, complex queries, repeated
  reductions, or shared query execution justify an analytical engine. Keep
  direct data-to-renderer paths when they are simpler and already fast enough.
  ([Apache Arrow][2])
- **Coordination and infrastructure.** Keep renderers and coordination layers
  replaceable. Use renderer-native capabilities for simple views. Consider
  Mosaic when linked selections, shared query coordination, or data-dependent
  reduction become substantial; Mosaic still describes itself as not yet
  production-ready. Treat `DatasetRef`, materialization DAGs, content
  identities, and build-system-style caching as optional internal
  optimizations. Introduce them only when reuse, provenance, or invalidation
  complexity justifies them. ([Mosaic][3])

[1]: https://quarto.org/
[2]: https://arrow.apache.org/
[3]: https://idl.uw.edu/mosaic/
