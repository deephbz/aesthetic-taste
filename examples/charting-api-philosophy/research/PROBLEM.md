# Problem: charting APIs as working environments for humans and agents

## Stage

This report is in **exploration**. Its goal is to find a useful comparison
shape. It is not a permanent benchmark or a universal ranking.

## Question

Starting from Matplotlib's object-oriented API, how do Vega, Vega-Lite,
Altair, Observable, D3, Observable Plot, Bokeh, Plotly, HoloViews,
Datashader, and Perspective lower prepared data into rendered output? Which
public checkpoints let an experienced author or agent inspect and change that
path safely?

## Context

The libraries are not eight substitutes for one plotting function. Some are
drawing systems, some are statistical interfaces, some are declarative
languages, some are browser model protocols, and some are data or application
ecosystems. A fair comparison must preserve these category differences.

The report uses one seven-layer vocabulary: authoring API, semantic IR,
reactive graph, graphical scene, renderer, output surface, and host graph. It
also shows coordinate lowering and interaction state where they occur.

The data is prepared before plotting. This removes chart-owned analytical
aggregation from the comparison. Seaborn remains a reference corpus, not a
primary runtime subject.

The supplied Chinese source is a useful hypothesis map about each project's
origin. Historical claims must still link to current primary sources.

## Desired result

- One canonical Jupytext source produces an executed notebook and Quarto HTML.
- Every named architecture has a dedicated or comparative section.
- The report distinguishes semantic IR, reactive graph, graphical scene,
  renderer, output surface, and surrounding host state.
- Agent ergonomics use edit, inspect, and avoid guidance instead of a ranking.
- Observed evidence, documented facts, and assessments remain separate.
- Important examples expose both a clean result and an inspectable artifact.
- The final report works without a Python server.
- One local Arrow IPC dataset supplies pandas, AG Grid, Perspective, and a
  histogram without embedding four copies of the rows.
- The standalone AG Grid, Perspective, and Bokeh examples remain intact, and
  a separate section shows all three as clients of one Mosaic coordinator.
- The coordinated section loads Arrow into DuckDB-Wasm once. Mosaic owns query
  scheduling and filter predicates; each widget only adapts its final result.
- The Arrow section has the same semantic structure in JupyterLab and Quarto.
- A tree separates source data, transport, runtime representations, and DOM
  size for the Arrow section.
- The report states when an iframe is a deliberate isolation boundary and when
  a native or host-neutral fragment can replace it.

## Predicted findings

- Vega will make dataflow state and graphical scene state more explicit than
  the Python libraries.
- Vega-Lite and Altair will preserve semantic intent, but compilation will
  produce lower-level objects that must remain derived output.
- Matplotlib's object API will provide the clearest retained-object analogy.
- Observable cells and Vega signals will prove to be different graph nodes at
  different runtime boundaries.
- Bokeh and Plotly will both expose browser-ready model state. Bokeh will make
  model identity and linked sources explicit; Plotly will make the figure
  protocol easy to serialize but large to navigate.
- Perspective will be strongest when the task is table transformation and
  exploration, not when judged only as a chart grammar.
- HoloViews will provide a semantic object layer, while Datashader will break
  the assumption that one row maps to one retained graphical object.
- A shared Arrow file will make data identity clearer than embedded rows, but
  JupyterLab and static HTML will need different URI resolution adapters.

These are predictions, not conclusions.

## Failure modes

- A single scatterplot ranking erases each system's native purpose.
- API line counts become a false quality or performance score.
- The report quotes origin stories without primary-source support.
- Interactive output silently depends on a live Python kernel.
- generated specifications or model graphs are displayed without bounded size.
- An ordinal score hides category differences or reflects taste.
- HoloViz is treated as one plotting library, or Vega-Lite as a Python package.
- JupyterLab and Quarto render different content because one path depends on a
  notebook widget manager or a Python callback.
- A browser view embeds a private copy of the 1,600 rows instead of fetching
  the versioned Arrow artifact.

## Acceptance

- The design artifact exists before report implementation.
- The report has no notebook execution errors.
- All named architectures are covered by name and category.
- Matplotlib, Altair/Vega-Lite/Vega, Bokeh, Plotly, Perspective, HoloViews,
  and Datashader execute against the same deterministic prepared dataset.
- One browser lab distinguishes Observable runtime, D3, and Observable Plot.
- The markout Arrow file has exactly 1,600 unique trades and a recorded hash.
- pandas, AG Grid, Perspective, and the Bokeh histogram all read that file.
- Each table exposes 1,600 rows, and the histogram bins total 1,600.
- The Mosaic section has one DuckDB-Wasm table, one shared filter selection,
  three custom clients, and one physical detail query for two table clients.
- Filtering the Mosaic section updates both tables and the histogram to the
  same independently checked row total.
- The Arrow section passes in both JupyterLab and Quarto-rendered HTML.
- The Arrow section uses no iframe and makes one Arrow HTTP request per host.
- The size receipt records both hosts and labels serialization sizes separately
  from heap memory.
- Reusable report inspection, rather than this report, owns the rendered
  artifact-size and parsed-DOM view.
- The iframe decision keeps all four markout projections in the host DOM and
  keeps a separate document only as a documented fallback.
- The HTML loads in a clean browser with no missing local report resources.
- A machine-readable evaluation record supports the agent assessment.
- The result artifact states what surprised us, what changed, and all limits.
