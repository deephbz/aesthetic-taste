# Result: executable API-to-pixels architecture guide

## Outcome

The report now follows the seven-layer model in 'ARCHITECTURE-GUIDE.md'. It no
longer presents eight libraries as one scored contest. Each major section shows
an authoring source, a lowering path, a public inspection point, and a rendered
verification signal.

The canonical report starts with Matplotlib's object-oriented API and prepared
data. Seaborn remains a short statistical-example reference. The interactive
labs then cover Bokeh and Plotly, Altair through Vega-Lite and Vega, Observable
Runtime with D3 and Observable Plot, HoloViews with Datashader, and Perspective.
The new data-plane section uses one Arrow IPC file for pandas, AG Grid,
Perspective, and a Bokeh histogram.
It preserves those independent adapters. A new section then uses Mosaic as a
shared analytical plane for a second AG Grid, Perspective table, and Bokeh
histogram.

## Findings

- Matplotlib's Artist hierarchy is a useful retained-object reference, but a
  PathCollection can represent many rows. It is not a one-row scene node.
- Altair and Vega-Lite preserve semantic intent. Compiled Vega exposes another
  program, a dataflow graph, signals, and a scenegraph. Compiled Vega stays
  derived unless the project explicitly changes its source language.
- Observable cells, Vega signals, and graphical scene items are three different
  kinds of state. The browser lab changes one Observable variable and shows a
  dependent Plot DOM update beside an explicit D3 DOM mutation.
- Bokeh exposes model identity and linked selection. Plotly exposes a stable
  figure protocol while keeping its renderer private.
- HoloViews preserves semantic objects before backend lowering. Datashader
  replaces per-row geometry with a screen-space aggregate and raster.
- Perspective exposes Table, View, viewer, and plugin boundaries. Its example
  now loads prepared rows with no grouping or aggregation.
- Arrow IPC gives the four markout projections one durable data identity.
  pandas reads the local file through PyArrow. The browser projections fetch
  the same URI through host-specific transport adapters.
- AG Grid and Perspective are both useful full-table projections. AG Grid owns
  a virtualized row model. Perspective owns a typed Table and View plus saved
  viewer state. Neither owns the source dataset.
- The Bokeh document can start with an empty source. Browser code can then load
  Arrow, calculate fixed histogram bins, and update that public model.
- One source artifact still produces multiple browser representations. AG Grid
  and Bokeh each retain Arrow plus about 403 KiB of JSON-equivalent row objects.
  Perspective accepts Arrow directly and creates no adapter-owned JSON row copy.
- AG Grid virtualized 1,600 model rows into 24 measured row nodes. pandas used
  20,821 DOM elements because its full table is literal HTML.
- The markout section now uses host-neutral `BrowserFragment` outputs. AG Grid
  uses our container adapter, Perspective uses its custom element, and Bokeh
  embeds a JSON item. A separate browser document remains an isolation fallback.
- One host promise reduced three Arrow requests to one. Each adapter receives a
  buffer copy, so a worker cannot detach bytes needed by another view.
- The Mosaic lab inserts the Arrow data into one DuckDB-Wasm table. One shared
  Selection owns symbol, side, venue, and liquidity filters.
- Mosaic consolidated the AG Grid and Perspective detail clients. Two logical
  clients caused one physical detail query. Bokeh received a separate 48-row
  SQL histogram result.
- The source Arrow artifact is IPC file format. Flechette converts it to IPC
  stream format once at the DuckDB-Wasm insertion boundary.

## Verification

- Clean execution: 19 of 19 code cells ran with zero error outputs.
- Quarto render: 27 report sections, 48 outputs, and 13 static resources.
- CLI inspection: status 'passed'; rendered report HTML size is 948,332 bytes.
- Parsed HTML contains 32,891 DOM nodes. Inspection reported no errors and 48
  size or serialization warnings.
- Quarto browser: six isolation labs and three native markout fragments loaded
  with zero console errors and zero warnings.
- JupyterLab browser: the trusted executed notebook loaded the same native
  fragments with zero console errors and zero warnings.
- Markout data: 1,600 rows, 12 columns, 180,618 bytes, and SHA-256
  `fc7d489d60255bab7d875be3ea7b677d8d86184d8f7a6e478d07e198edf85090`.
- Both hosts reported 1,600 pandas rows, 1,600 AG Grid rows, 1,600 Perspective
  rows, and a 1,600-row Bokeh histogram total.
- Both hosts made one Arrow request and contained zero markout iframes.
- The existing `window.MARKOUT_*` inspection API remained available.
- The Mosaic API reported 1,600 equal rows at load. Its initial three logical
  clients caused two physical queries: one detail query and one histogram.
- The NVDA filter produced 325 AG Grid rows, 325 Perspective rows, a 325-row
  histogram total, and a direct SQL count of 325.
- A one-second to five-second horizon change caused only one new histogram
  query. It did not rerun either detail client.
- Perspective's markout config stayed verbatim: no grouping, split, filter,
  sort, or aggregate state.
- Changing the JupyterLab histogram from one second to five seconds preserved
  the 1,600-row bin total.
- The browser-specific markout receipt separates Arrow, Python memory,
  fragments, row representations, shadow DOM, and virtual rows.
- Saved-artifact and parsed-DOM inspection moved to the reusable `report
  inspect` command. Its JSON is canonical, and `report.inspect.html` is a
  derived human view. Browser-specific measurements remain a separate receipt.
- Vega: the public View reported SVG output, named signals, and 2,596 scene items.
- Observable: selecting 'search' recomputed the dependent value from 2,400 to
  601 rows; the D3 view retained 2,400 circle nodes.
- Bokeh: setting three selected indices updated the shared Selection model and
  the linked status display.
- Perspective: 2,400 rows loaded; 'viewer.save()' returned no grouping and no
  aggregates; viewer Wasm and server memory64 Wasm loaded.

## Durable artifacts

- 'report.py': canonical Jupytext source and artifact generators.
- 'ARCHITECTURE-GUIDE.md': detailed conceptual guide and source-linked claims.
- 'report.executed.ipynb': executed evidence.
- 'report.rendered.html': Quarto publication.
- 'data/markouts.arrow': versioned HTTP-readable trade fixture.
- 'artifacts/': nine kernel-free interactive labs.
- 'evidence/comparison-records.json': data identity, versions, lowering traces,
  agent edit guidance, and limits.
- 'evidence/markout-data-receipt.json': Arrow schema, size, hash, and histogram
  invariant.
- 'evidence/markout-size-tree.json': composed DOM and data-size measurements in
  Quarto and JupyterLab.
- 'evidence/mosaic-coordinator-contract.json': shared state, query, and renderer
  invariants.
- 'evidence/report-inspection.json': canonical JSON whole-report inspection.
- 'report.inspect.html': derived human artifact tree and parsed-DOM view.
- 'evidence/browser-acceptance.json': observed runtime and interaction checks.
- 'evidence/report-browser.png': accepted viewport capture.
- 'output/playwright/': Quarto and JupyterLab markout screenshots.
- 'report.inventory.json': CLI source, execution, and render inventory.

## Limits

This remains an exploration-stage lesson. The markout dataset is deterministic
synthetic data, not trading-performance evidence. The report is not a renderer
throughput test or an autonomous-agent benchmark. Observable, Plotly,
Perspective, AG Grid, and Arrow JS use pinned CDN modules. Perspective needs
static HTTP for ESM, worker, and Wasm. JupyterLab must trust saved HTML output
before fragment scripts run. Dynamic HoloViews, Datashader, or Panel
applications can still need live Python.
