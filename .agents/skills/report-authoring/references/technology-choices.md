# Technology choices

Own dated architecture advice for report architecture. Read this when selecting
data interchange, browser compute, or coordination infrastructure. The
[report contract](../../../../docs/report-contract.md) owns the requirements.

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
