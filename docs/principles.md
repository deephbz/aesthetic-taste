# Principles

## Scope:

- **Immutable, read-only data boundary.** Treat upstream data production as an external black box that publishes immutable data artifacts; dashboards consume and transform them without writing back.
- **Artifact-first deployment.** Prefer self-contained static artifacts or bundles (e.g. html + js + wasm + data files) that can be stored, served, copied, and reopened without an application service.
- **Backendless by default.** Stick with static file transport over application services. E.g. server-side compute, databases, authentication, or persistent application state at server side are not required by default unless explicitly required by user and workload type.
- **Browser-first execution.** Keep latency-sensitive interaction and analytical work close to the browser when practical; move computation elsewhere only when workload constraints justify it.


## Data, State and Compute

- **Report data boundary.** Separate large upstream data from report-resident data; materialize only the bounded data required for report consumption and browser-side exploration, while keeping expensive or large-scale transformations upstream.
- **Explicit, reproducible transformation.** Model analytical results as reproducible transformations of explicit inputs where practical, while keeping external effects and environment-dependent behavior at clear system boundaries.
- **Reconstructible derived state.** Treat caches and materialized computation as non-authoritative accelerators that may be discarded and rebuilt from durable inputs; choose caching, identity, and invalidation mechanisms according to the workload and avoid premature/over-engineering.
- **Portable semantic view state.** Keep shareable view state independent of renderer-specific state, and allow selected valid state to be serialized into portable representations such as the URL; keep renderer adapters and transient interaction state non-authoritative.

```
```hierarchy:
DATA / COMPUTE                          VIEW

durable immutable inputs              portable view state
        ↓                                     ↓
reproducible transformation           transient interaction
        ↓                                ↓
reconstructible materialization ──→   rendered view
```

## Visual 

- **Notebook-to-web semantic parity.** Preserve the same report data, visualization, interaction, and view-state semantics across JupyterLab and Quarto-rendered HTML, while allowing environment-specific adapters.
```
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
```
```

- **Recoverable/Durable reporting.** Interactive rendering should not be the sole source of analytical meaning; preserve enough durable inputs, source, and provenance to reconstruct important report outputs when needed. This is ONLY required when explicitly asked by user.
```DurabilityLayers
Level 1 — Reconstructible
immutable data + source + provenance
        ↓
can regenerate

Level 2 — Cheap automatic fallback
generated static snapshot/table
        ↓
readable without rich runtime

Level 3 — Fully archival artifact
self-contained, frozen dependencies,
multiple representations
```
```
```

## Performance

- **Efficient analytical data representation.** Prefer compact, columnar, and zero- or low-copy data representations for large analytical workloads; use row-oriented or textual formats when their simplicity is more valuable than throughput.
- **Working-set proportionality.** Keep latency-sensitive browser computation, transfer, and rendering proportional to the current analytical view rather than the full available dataset; perform reduction at the most appropriate layer for the workload.

I would add a clearly non-normative section like this:

# Architecture Guidance — 2026

* **Authoring and publication.** Use JupyterLab as the literate research and execution environment, and Quarto as the default publication layer for static HTML reports. Quarto supports Jupyter-native authoring and client-side interactive widgets, while published HTML does not require a Python kernel. ([Quarto][1])

* **Data and browser compute.** Prefer Arrow IPC for compact browser-ready interchange and Parquet for larger, partitioned, or query-oriented datasets; add DuckDB-Wasm only when browser-side joins, complex queries, repeated reductions, or shared query execution justify an analytical engine. Keep direct data-to-renderer paths when they are simpler and already fast enough. ([Apache Arrow][2])

* **Coordination and infrastructure.** Keep renderers and coordination layers replaceable: use renderer-native capabilities for simple views, and consider Mosaic when linked selections, shared query coordination, or data-dependent reduction become substantial; Mosaic itself still describes the project as not yet production-ready. Treat `DatasetRef`, materialization DAGs, content identities, and build-system-style caching as optional internal optimizations that should be introduced only when reuse, provenance, or invalidation complexity justifies them. ([UW Interactive Data Lab][3])
