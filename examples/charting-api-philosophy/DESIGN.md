# Design: from authoring API to pixels

## Stage and source allocation

The report is in exploration. `PROBLEM.md` owns the question and predictions.
`ARCHITECTURE-GUIDE.md` owns the current conceptual model and primary-source
research. This file owns the executable lesson design. `report.py` owns the
examples and derived traces. `RESULT.md` owns the accepted result and evidence.

The architecture guide replaces the former ordinal scorecard as the report's
main teaching structure. Scores can hide category errors. The new report uses
observable lowering paths and inspection points.

## Ontology

- `AuthoringProgram`: the public code or specification an author edits.
- `SemanticIR`: a retained statement of visual intent before screen geometry.
- `ReactiveGraph`: dependencies that recompute data or visual properties.
- `GraphicalScene`: retained graphical objects or scene items.
- `Renderer`: code that converts graphical state into an output surface.
- `OutputSurface`: SVG, Canvas, WebGL, bitmap, vector file, or notebook display.
- `HostGraph`: state outside the chart runtime, such as Observable cells,
  Jupyter widgets, Panel parameters, or application state.
- `CoordinateLowering`: transforms from data values to screen coordinates.
- `InteractionState`: a semantic selection, filter, range, or focus value.
- `InspectionPoint`: a public checkpoint that an agent can query and verify.
- `PublicationBoundary`: runtime resources that remain after Python stops.
- `DatasetArtifact`: one typed, immutable Arrow IPC file used by all projections.
- `DataURL`: the browser-resolvable URI of that artifact.
- `Projection`: a table or chart that reads the DatasetArtifact without becoming
  a second data authority.
- `BrowserFragment`: scoped HTML plus dependencies and a mount operation for the
  host document.
- `BrowserDocument`: a complete isolated HTML document mounted through an
  iframe when isolation is necessary.
- `AnalyticState`: the report-owned filter and horizon values that can be
  serialized without retaining library objects.
- `QueryCoordinator`: Mosaic's browser runtime that compiles shared selection
  predicates, schedules DuckDB queries, and routes results to clients.
- `RendererClient`: a thin adapter whose query declares one result shape and
  whose result handler updates AG Grid, Perspective, or Bokeh.

These nouns form the neutral path:

```text
prepared data + authoring program
              |
              v
semantic IR -> reactive graph -> graphical scene -> renderer -> output surface
                     ^                    ^
                     |                    |
                host state          coordinate lowering
```

Not every system exposes every layer. A missing public layer is an architectural
fact, not a defect.

## Educational comparisons

The report uses Matplotlib's object-oriented API as the reference model. It
does not teach pyplot state. It compares these specific distinctions:

1. Matplotlib `Artist` hierarchy versus a neutral graphical scene.
2. Vega-Lite semantic specification versus compiled Vega runtime state.
3. Vega signal versus Observable cell or variable.
4. Vega mark definition versus concrete mark items.
5. D3 DOM mutation versus Observable Plot's mark objects.
6. Bokeh serializable model graph versus Plotly's public figure protocol.
7. HoloViews semantic objects versus backend models.
8. Datashader screen-space aggregation versus per-row retained geometry.
9. Perspective Table, View, viewer state, and plugin boundary.

Seaborn remains a short reference. Its main value here is a corpus of useful
statistical examples, not a new rendering architecture. All chart-owned
aggregation is excluded from the core examples. Polars or SQL would normally
prepare aggregates before rendering; this report uses deterministic pandas
tables because the focus is architecture.

## Executable lesson contract

Each major runtime section must show four things:

```text
EDIT     the canonical public source
LOWER    through named intermediate layers
INSPECT  one public runtime or serialized checkpoint
VERIFY   a visible output or semantic state change
```

The common prepared request table supplies values and a separately computed
p95 reference. A library must not compute the p95 inside the chart grammar.
The report can use library-native filtering for interaction, but it must label
that as runtime state rather than analytical preparation.

## Interactive labs

The report publishes these kernel-free labs:

- Altair/Vega-Lite: select a service, then inspect the generated Vega-Lite
  specification and the browser Vega View state.
- Observable runtime, D3, and Plot: change one host variable and observe a cell
  dependency update, a direct DOM update, and a regenerated Plot DOM tree.
- Bokeh: select points in one view and observe shared `ColumnDataSource` state
  in a second view.
- Plotly: inspect the stable `data/layout/frames` figure roots and browser event
  payloads.
- HoloViews: inspect the semantic object and the resolved Bokeh model.
- Datashader: inspect the aggregate array and the shaded raster.
- Perspective: inspect a saved ViewerConfig over prepared rows. Do not use a
  group-by example as the central lesson.
- Local Arrow loading: read one 1,600-row trade file through pandas, AG Grid,
  Perspective, and a Bokeh histogram. AG Grid and Perspective show all rows
  through virtualization. The pandas projection includes all rows in a bounded
  scroll region. The Bokeh histogram computes bins after the same Arrow fetch.
- Mosaic coordination: preserve the standalone projections, then load the same
  Arrow file once into DuckDB-Wasm. One shared Mosaic selection drives two
  identical detail clients and one SQL histogram client. AG Grid receives row
  objects, Perspective receives Arrow IPC, and Bokeh receives 48 aggregate
  rows. The system-owned plain state remains the serializable contract.

## Markout dataset contract

No markout dataset exists in the workspace. The exploration therefore creates
one deterministic synthetic fixture at `data/markouts.arrow`. It has exactly
1,600 trades and these stable field groups:

~~~text
identity    trade_id, executed_at
trade       symbol, side, venue, liquidity, quantity, price
outcomes    markout_50ms_bps, markout_250ms_bps,
            markout_1s_bps, markout_5s_bps
~~~

Markouts are signed from the trade side. Positive values are favorable to the
trade. The file is an Arrow IPC file, not embedded JSON. Python reopens it with
PyArrow before pandas display. Each browser projection fetches the same bytes.

The stable report-relative URI is `data/markouts.arrow`. Static HTTP resolves
it relative to `report.rendered.html`. A small adapter maps the same URI to the
Jupyter `/files/` route for default and named-workspace tree URLs. That adapter
is transport logic. It does not change dataset identity.

~~~text
deterministic generator
        |
        v
data/markouts.arrow + SHA-256
        |
        +--> PyArrow read --> pandas full-row HTML projection
        |
        +--> HTTP fetch --> Arrow JS --> AG Grid
        |
        +--> HTTP fetch --> Perspective worker --> Datagrid
        |
        +--> HTTP fetch --> Arrow JS --> explicit bins --> Bokeh source
~~~

All four projections must report 1,600 source rows. The histogram bin total
must also equal 1,600. Browser evidence must record the resolved Arrow URL.

The additive Mosaic section uses the same file but a different execution path:

~~~text
data/markouts.arrow
        |
        v
one DuckDB-Wasm table + one Mosaic coordinator
        |
        +--> identical detail SQL --> AG Grid row objects
        |                       \--> Perspective Arrow IPC
        |
        +--> histogram GROUP BY bin --> Bokeh source
~~~

The durable artifact uses Arrow IPC file format. DuckDB-Wasm's insertion API
accepts an IPC stream, so the shared loader performs one explicit Flechette
file-to-stream conversion before the one database insertion. This is transport
normalization, not a second analytical data authority.

The plain `AnalyticState` value owns selected side, venue, liquidity, and
markout horizon. A Mosaic `Selection` is its executable predicate projection,
not the durable application authority. Two identical detail queries must be
consolidated into one physical connector request. Browser acceptance compares
all three client totals with a direct DuckDB count query.

The reusable `report inspect` command owns saved-artifact and parsed-HTML size
inspection. Its JSON output is the machine authority, and its optional HTML is
the human projection. `evidence/markout-size-tree.json` remains the accepted
browser-specific measurement receipt. JSON-equivalent sizes are serialization
proxies, not heap measurements.

The current markout browser projections use `BrowserFragment`. AG Grid mounts
into a scoped container. Perspective mounts its public custom element. Bokeh
loads one pinned core script and embeds a JSON item. One host promise fetches
Arrow once and gives each adapter an isolated buffer copy. The adapters retain
the existing `window.MARKOUT_*` inspection surface. Keep `BrowserDocument` only
as the isolation fallback for incompatible CSS, dependencies, or security rules.

## Section plan

1. Teach the seven-layer neutral model and its non-equivalences.
2. Establish the prepared-data and semantic-state contract.
3. Use Matplotlib OO as the retained-object reference; place Seaborn aside.
4. Walk Altair to Vega-Lite, Vega, dataflow, scenegraph, and SVG or Canvas.
5. Separate Observable host reactivity, D3 DOM mutation, and Plot mark output.
6. Compare Bokeh's public model graph with Plotly's public figure protocol.
7. Trace HoloViews lowering and Datashader rasterization.
8. Treat Perspective as the Table/View/viewer/plugin boundary case.
9. Load one Arrow IPC trade file into pandas, AG Grid, Perspective, and Bokeh.
10. Reuse those renderers behind one Mosaic and DuckDB-Wasm query plane.
11. Give a vocabulary crosswalk and agent edit/inspect/avoid guidance.
12. Record runtime and browser evidence, publication limits, and conclusions.

## Agent-use evaluation

The report does not compute a universal score. It records three practical
questions for each system:

- What should an agent edit?
- What public artifact or state should it inspect?
- What private or derived state should it avoid making authoritative?

This form preserves system categories and makes the next action clear.

## Evidence graph

```text
ARCHITECTURE-GUIDE.md + architecture-source-notes.json
                         |
prepared data ---------->+--> report.py
                               |
             +-----------------+----------------+
             |                 |                |
       Python traces     browser labs      saved configs
             |                 |                |
             +------> comparison-records.json <-+
                               |
                    executed notebook -> Quarto HTML
                               |
                    browser acceptance receipt
```

## Evidence rules

- `observed`: produced by report execution or browser validation.
- `documented`: supported by a linked primary source.
- `assessed`: an interpretation derived from observed and documented facts.
- Construction time and file size are diagnostics, not performance rankings.
- The report must show clean results and bounded debug traces.
- Private runtime fields can help diagnosis, but they cannot become the public
  authoring contract.

## Publication boundary

The final Quarto HTML must not call Python. Inline Bokeh and Vega artifacts can
run without a server process. CDN-backed Plotly, Observable, AG Grid, Arrow JS,
and Perspective labs need network access. Perspective also needs static HTTP
for module, worker, and Wasm loading.

The markout browser projections must use host-native fragments with scoped CSS.
The data adapter must resolve the Arrow file through Jupyter's `/files/` route
or ordinary report-relative static HTTP. The host must make one Arrow request.
Browser acceptance must test both hosts with no markout iframe.
