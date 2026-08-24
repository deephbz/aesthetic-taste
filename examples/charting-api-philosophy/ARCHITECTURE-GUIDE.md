# From API to pixels: a cross-library architecture guide

## Scope

This guide assumes that Polars or SQL already produced the final rows and
columns needed for display. Plotting libraries do not own business
aggregation, statistical estimation, pivoting, or reshaping in this model.

The reference system is Matplotlib's object-oriented API. Stateful pyplot is
out of scope. HoloViews is a second reference because its semantic objects and
backend lowering are already familiar.

Seaborn, Plotly Express, hvPlot, and Observable Plot's automatic transforms can
still serve as agent recipe corpora. They are not the architectural center of
this study.

This is a shaping-stage guide. It defines the vocabulary and learning path for
a later executable walkthrough.

## 1. The model to keep in your head

Do not assume that every visualization system has one public scenegraph.
Separate these seven layers first:

```text
Domain computation
Polars / SQL / application code
        |
        v
Prepared data + semantic interaction state
        |
        v
1. Authoring API
   Calls, objects, or JSON written by the author
        |
        v
2. Semantic intermediate representation
   What visual elements and encodings should exist
        |
        v
3. Reactive or dataflow graph
   What must recompute when data or state changes
        |
        v
4. Graphical scene
   Concrete visual instances with geometry and style
        |
        v
5. Renderer
   Converts geometry and style into drawing operations
        |
        v
6. Output surface
   SVG DOM, Canvas bitmap, WebGL framebuffer, PNG, PDF

7. Host or application graph surrounds the pipeline
   Notebook cells, widgets, application state, routing, persistence
```

A library can collapse several layers. It can hide them. It can omit them.
It can also delegate them to another library.

This distinction matters because agents need a stable edit target and a stable
verification target. A private scenegraph is useful for debugging. It is a bad
source of truth.

## 2. Neutral vocabulary

### Authoring API

The surface a human or agent writes. Examples include `Axes.scatter`, a Vega
JSON object, a Bokeh `figure`, or a Plotly `Figure`.

### Semantic intermediate representation

A representation that still carries chart meaning. It can say “points encode
`x` and `y`” without containing final screen coordinates. Vega-Lite specs,
Plotly figures, HoloViews Elements, and Bokeh Models all retain different
amounts of semantic meaning.

### Reactive or dataflow graph

A dependency graph for computation. Its nodes contain values or operations.
Edges say what must update when an input changes. A reactive graph is not a
graphical scene.

Vega dataflow operators and Observable cells belong here.

### Graphical scene or scenegraph

A retained structure of graphical instances. Nodes or items usually contain
resolved geometry, transforms, style, clipping, visibility, and parent-child
relations.

Matplotlib's official term is Artist hierarchy. It is scenegraph-like. Vega
explicitly exposes a scenegraph. An SVG DOM is also a retained graphical tree.

### Immediate rendering

Code emits drawing commands directly to a Canvas or WebGL context. The library
can retain data and state without retaining one public graphical tree.

### Renderer

This word is overloaded. It can mean a low-level painter, a backend adapter, a
model that connects data to glyphs, or a notebook display policy. Always ask:
“What input does this renderer accept, and what output does it produce?”

### Host state

State that determines when a visualization is rebuilt or how multiple views
coordinate. Observable cells, Jupyter widgets, Panel Parameters, and an
application's selection store are host state. They are not automatically part
of the chart's scene.

### Coordinate lowering

Every system must eventually convert abstract values into device coordinates.
Keep this path separate from data aggregation:

```text
domain value
   |
scale or coordinate transform
   |
plot-frame coordinate
   |
layout transform
   |
device pixel or vector coordinate
   |
clipping and compositing
```

Matplotlib exposes a transform stack between data, Axes, Figure, and display
coordinates. Vega uses named scales and encoders before scenegraph items are
drawn. Bokeh combines ranges, scales, frames, and BokehJS Views. D3 commonly
calls scale functions explicitly before setting SVG attributes or Canvas draw
arguments. Plotly expresses axis domains and paper coordinates in the public
figure, then resolves pixels inside Plotly.js. HoloViews delegates this stage
to its selected backend.

An agent investigating wrong geometry must determine whether the fault is in
prepared data, a scale domain, a coordinate transform, layout, or renderer
clipping. “The point is in the wrong place” does not identify a layer.

### The output surface does not define the authoring model

SVG, Canvas, and WebGL preserve different evidence:

```text
SVG
  retained DOM nodes -> browser vector renderer -> pixels
  strong element inspection; high DOM cost for many items

Canvas 2D
  immediate draw calls -> bitmap
  no retained semantic node per mark; application must redraw

WebGL
  arrays -> GPU buffers -> shaders -> primitives -> framebuffer
  high throughput; weak semantic inspection after upload

PNG
  final pixels only

PDF / SVG file
  retained vector drawing operations, but not necessarily source semantics
```

A library can keep a rich public model while drawing to Canvas. Bokeh is an
example. A library can expose almost no intermediate chart model while using a
rich SVG DOM. D3 code can do that. Never infer the authoring architecture from
the final surface alone.

## 3. Matplotlib as the reference

The object-oriented path is:

```text
Figure / Axes methods
        |
        | construct and register
        v
Artist hierarchy
Figure
└── Axes
    ├── PathCollection
    ├── Line2D
    ├── Text
    ├── Axis
    └── Patch
        |
        | draw(renderer)
        v
FigureCanvas + Renderer
        |
        v
Agg pixels / SVG / PDF / GUI surface
```

The Artist is both retained state and drawing participant. It owns visual
properties and knows how to ask a renderer to paint them. The backend owns the
surface-specific operations. This is the documented FigureCanvas, Renderer,
and Artist split in the
[Matplotlib Artist tutorial](https://matplotlib.org/stable/tutorials/artists.html).

The main inspection path is the live Python object hierarchy:

```python
for artist in ax.get_children():
    print(type(artist).__name__, artist.get_visible(), artist.get_zorder())
```

An agent can mutate an exact object and redraw. The same object graph is not a
portable language-neutral protocol. Pickling it is not equivalent to a Vega or
Plotly specification.

## 4. Vega: the system with the most explicit layers

Vega is the best system for learning the distinctions in this guide. It has a
declarative specification, a reactive dataflow runtime, a scenegraph, and
multiple renderers.

### 4.1 The full path

```text
Vega JSON specification
  data, transforms, scales, signals, marks, axes, legends
        |
        | vega.parse(spec)
        v
Runtime dataflow description
        |
        | new vega.View(runtime)
        v
Reactive dataflow graph
  data operators
  transform operators
  signal operators
  scale operators
  encoders
        |
        | pulse propagation and encoding
        v
Vega scenegraph
  group items
  mark items
  resolved x/y/fill/stroke/opacity/path values
        |
        v
SVG renderer or Canvas renderer
        |
        v
SVG DOM or Canvas bitmap
```

The [Vega parser](https://vega.github.io/vega/docs/api/parser/) converts the
specification into a runtime dataflow description. A
[`View`](https://vega.github.io/vega/docs/api/view/) instantiates that dataflow,
runs it, maintains scenegraph state, handles events, and renders output.

### 4.2 A mark is a definition for a set of graphical items

A Vega mark is not exactly one Matplotlib Artist.

```text
Vega mark definition
  type: symbol
  from: points
  encode: x, y, fill, size
        |
        | one backing tuple can create one item
        v
Vega scenegraph mark items
  item 0: x=83,  y=120, fill=#2764ae
  item 1: x=101, y=92,  fill=#0d7c76
  item 2: x=144, y=210, fill=#2764ae
```

The mark definition is closer to a vectorized Artist factory plus an encoding
rule. A mark item is closer to a concrete graphical node. The
[Vega marks documentation](https://vega.github.io/vega/docs/marks/) distinguishes
mark definitions, backing data, encode sets, and generated scenegraph items.

The `enter`, `update`, and `exit` encode sets describe lifecycle-sensitive
property evaluation. They echo D3's data join vocabulary, but Vega executes
them inside its dataflow runtime.

### 4.3 Signals are reactive scalar variables

A Vega signal is a named dynamic value inside the Vega runtime.

```text
pointermove event
      |
      v
event stream
      |
      v
signal: cursorX
      |
      +--> scale inversion
      +--> mark opacity expression
      +--> filter or transform parameter
      |
      v
dataflow pulse -> dirty scenegraph items -> redraw
```

Signals can update from event streams, upstream signals, or the `View` API.
Their values propagate through dependent operators. See
[Vega signals](https://vega.github.io/vega/docs/signals/) and
[event streams](https://vega.github.io/vega/docs/event-streams/).

The closest Matplotlib analogy is not an Artist. It is an application-owned
observable variable connected to Artist setters and `draw_idle()`. Matplotlib
does not provide one equivalent declarative signal graph.

### 4.4 Dataflow and scenegraph are different graphs

This is the most important Vega distinction.

```text
Reactive dataflow graph                    Graphical scenegraph

signal operator                            root group item
      |                                    ├── axis group
scale operator                             ├── legend group
      |                                    └── symbol mark
encoder operator                               ├── item
      |                                        └── item
scenegraph data join
```

The dataflow graph answers “what recomputes?” The scenegraph answers “what is
currently drawable?”

Use public inspection before private internals:

```javascript
view.signal("brush")
view.data("points")
view.getState()
view.scenegraph().root
```

Vega's [debugging guide](https://vega.github.io/vega/docs/api/debugging/)
documents these paths. It labels `view._runtime` as internal. Agents can read
it during diagnosis, but they must not write code that depends on it.

### 4.5 Scales, axes, and legends

A scale is a named mapping from a data domain to a visual range. Marks consume
scales. Axes and legends visualize scales. They are not the scales themselves.

```text
data values -> scale function -> visual values -> mark items
                    |
                    +--> axis or legend generator -> more scenegraph items
```

This differs from Matplotlib, where an `Axis` is a retained Artist container
that also owns ticks, labels, and scale-related behavior.

### 4.6 Agentic implications

Vega gives an agent four useful checkpoints:

1. Diff the Vega specification.
2. Inspect named data and signals through the `View` API.
3. Inspect scenegraph items when geometry is wrong.
4. Verify SVG or Canvas output in a browser.

The danger is editing compiled runtime operators or scenegraph items as source.
Those are derived state.

## 5. Vega-Lite and Altair: a compiler frontend, not another renderer

The path adds two layers above Vega:

```text
Altair Python objects
        |
        | to_dict() / to_json()
        v
Vega-Lite specification
  mark, encoding, composition, parameters
        |
        | Vega-Lite compile
        v
Vega specification
        |
        v
Vega dataflow -> scenegraph -> SVG or Canvas
```

Altair is a typed and validated Python constructor for Vega-Lite. Vega-Lite is
a higher-level language that expands into Vega. Neither one owns a separate
scenegraph.

A Vega-Lite `mark: "point"` is a compact semantic instruction. Compilation can
create multiple Vega marks, scales, guides, signals, and data sources.

A Vega-Lite selection parameter is a declarative data query driven by direct
manipulation. It is not just one Vega signal. Compilation can create signals,
selection stores, event handlers, predicates, and scale-domain wiring. See
[Vega-Lite selection parameters](https://vega.github.io/vega-lite/docs/selection.html).

For agent work, preserve both specifications when debugging:

```text
authored.vl.json       human and agent intent
compiled.vega.json     compiler expansion evidence
runtime state          observed signals and named data
scenegraph snapshot    geometry evidence when needed
```

Do not ask an agent to modify compiled Vega unless the project has deliberately
crossed the escape hatch and made Vega the new source language.

## 6. Observable is three different architectural subjects

“Observable” can refer to the notebook runtime, Observable Plot, or the company
and hosting products. D3 is another library. Do not merge their vocabularies.

### 6.1 Observable notebook runtime: a reactive program graph

Observable notebook cells are reactive variables in a module dependency graph.

```text
Input widget value
       |
       v
cell: selectedService
       |
       +--> cell: filteredRows
       |          |
       |          v
       +------> cell: chart
                       |
                       v
                 returned DOM node
                       |
                       v
                    Inspector
```

When an upstream cell changes, dependent cells re-evaluate. The runtime does
not require a chart scenegraph. A cell can return a number, Arrow table,
Promise, DOM element, Plot figure, or anything else.

Observable calls these cells or variables, not Vega signals. The
[Observable runtime](https://github.com/observablehq/runtime) connects variables
into a dependency graph. The
[Observable JavaScript guide](https://observablehq.com/documentation/cells/javascript)
explains topological execution and reactive re-evaluation.

A Vega signal can live inside a Vega `View` returned by one Observable cell.
The Observable runtime then surrounds the Vega runtime. They remain two
different reactive systems.

### 6.2 D3: data-driven mutation of browser graphics

D3 is a collection of modules. It does not prescribe one retained D3
scenegraph.

For SVG, the common path is:

```text
D3 scales, shape generators, layouts
        |
D3 selection + data join
        |
create or mutate SVG DOM nodes
        |
browser SVG renderer
        |
pixels
```

The SVG DOM is the retained graphical tree. A D3 selection is a wrapper over
DOM nodes. Bound data is stored on those nodes. Enter, update, and exit describe
the relation between data tuples and DOM elements. See
[D3 selections](https://d3js.org/d3-selection) and
[data joins](https://d3js.org/d3-selection/joining).

For Canvas, D3 can compute scales, paths, layouts, or colors, then user code
issues immediate drawing commands. The DOM no longer contains one node per
graphical item. The application must retain enough data and state to redraw.

This makes D3 unusually flexible and unusually dependent on local program
structure. An agent cannot assume that “inspect the D3 scenegraph” is a valid
operation.

### 6.3 Observable Plot: mark objects that produce DOM

Observable Plot is a concise grammar-of-graphics-style library built with D3.

```text
Plot.plot options
  marks, channels, scales, facets
        |
        v
Plot Mark objects
        |
        | initialize, scale, render
        v
SVG or HTML figure element
        |
        v
browser DOM rendering
```

`Plot.dot(...)` returns a mark object. One mark can produce many graphical
shapes. `Plot.plot(...)` returns an SVG or HTML figure element. See
[Observable Plot marks](https://observablehq.com/plot/features/marks) and
[plots](https://observablehq.com/plot/features/plots).

Plot's mark is not Vega's mark definition. Both describe geometric vocabulary,
but Plot lowers directly into DOM output through its JavaScript implementation.
It does not expose Vega's specification compiler, reactive dataflow graph, or
scenegraph API.

For prepared columnar data, Plot can accept separate channel arrays. This avoids
some tidy-data assumptions, although Plot still owns scale inference and mark
defaults unless the author specifies them.

### 6.4 Agentic implications

Separate three edit targets:

- Observable cell source controls host dependencies.
- Plot options and marks control a generated chart.
- D3 code controls DOM or Canvas mutation directly.

For SVG output, DOM inspection is a strong verification signal. For Canvas,
the application needs its own structured trace because pixels do not expose
the authoring structure.

## 7. Bokeh: a serializable application model graph

Bokeh is closer to Matplotlib than Vega is, but its public retained structure
is a graph of application Models rather than a hierarchy of drawing Artists.

### 7.1 Full path

```text
Bokeh Python API
figure(), glyph methods, layouts, tools
        |
        v
Bokeh Model graph in a Document
  Plot
  Range1d
  ColumnDataSource
  GlyphRenderer -> Glyph
  Axis, Grid, Tool, Selection
        |
        | serialize references and properties
        v
BokehJS Model graph
        |
        | create corresponding Views
        v
layout + coordinate mapping + canvas glyph drawing
        |
        v
HTML Canvas, optional WebGL, and DOM overlays
```

A Bokeh `Document` owns root Models and every Model reachable through their
references. The document can select Models, validate them, and serialize them.
See the [Document API](https://docs.bokeh.org/en/latest/docs/reference/document/document.html)
and [document model manager](https://docs.bokeh.org/en/latest/docs/reference/document/models.html).

### 7.2 Glyph, GlyphRenderer, Model, and View

These names need care:

```text
ColumnDataSource
       |
       v
GlyphRenderer ----> Glyph model
       |
       v
BokehJS GlyphRendererView
       |
       v
Canvas or WebGL drawing
```

The Glyph defines visual properties. The `GlyphRenderer` connects a data
source, glyphs, selection policy, and rendering level. Despite its name, it is
not analogous to Matplotlib's `RendererAgg`. It is closer to a retained visual
layer or Artist factory.

The BokehJS View is the active browser counterpart that manages layout, DOM,
or drawing for a Model. Model properties are the serializable state boundary.

### 7.3 State and change propagation

Bokeh properties generate change events. Shared object identity is the core
linking mechanism:

```text
one ColumnDataSource.selected
          |
          +--> GlyphRenderer in plot A
          +--> GlyphRenderer in plot B

one Range1d
          |
          +--> x_range of plot A
          +--> x_range of plot B
```

`ColumnDataSource.selected` contains a `Selection` Model. In a standalone
document, JavaScript callbacks and links update browser-side Models. With a
Bokeh server, document patches can synchronize between BokehJS and Python.

### 7.4 Agentic implications

The public Model graph is an excellent agent target when identity matters.
Give important Models stable `name` values or tags. Then agents can use
`Document.select`, inspect properties, and serialize the document.

The main risks are:

- graph context grows because identity and references matter;
- CustomJS can hide behavior in code strings or modules;
- Python and JavaScript callbacks have different deployment boundaries;
- Canvas output has no DOM node for each glyph item.

An agent should modify Models, not BokehJS Views or Canvas internals.

## 8. Plotly: a public figure protocol over a private rendering runtime

Plotly's durable public object is the figure tree.

```text
graph_objects API
        |
        v
Figure schema tree
├── data: traces
├── layout: axes, subplots, annotations, shapes, controls
└── frames: animation updates
        |
        | JSON serialization
        v
Plotly.js defaults and calculation pipeline
        |
        v
trace-specific rendering modules
        |
        +--> SVG DOM
        +--> Canvas
        +--> WebGL
        +--> map or 3D scene subsystems
```

Graph Objects are generated Python classes for nodes in the machine-readable
Plotly figure schema. Plotly.js applies templates, defaults, axis calculations,
and trace-specific rendering. See
[Graph Objects](https://plotly.com/python/graph-objects/) and the
[figure structure](https://plotly.com/python/figure-structure/).

A Plotly trace is not one graphical primitive. One `Scatter` trace can produce
many markers, line segments, labels, hover targets, and a legend item. A trace
is closer to a typed visual layer protocol.

Plotly does not promise a single public scenegraph shared across SVG, WebGL,
3D, maps, and other trace systems. The browser DOM and private calculated state
are useful diagnostics, not a stable source API.

Interaction emits events such as `plotly_click`, `plotly_selected`,
`plotly_restyle`, and `plotly_relayout`. The update payload is an event or patch
protocol. It is not a reactive signal graph. See
[Plotly.js events](https://plotly.com/javascript/plotlyjs-events/).

### Agentic implications

Agents should edit and diff the public figure JSON. Python Graph Objects add
validation and good path-based errors. Verification can check trace arrays,
layout ranges, schema validity, emitted events, and final browser output.

Do not make private Plotly.js structures such as calculated full layout state
part of a durable contract. Different trace modules can use different internal
rendering systems.

## 9. HoloViews: semantic objects lowered through a backend registry

HoloViews is neither a scenegraph nor a graphics renderer. It is a semantic
object and composition layer.

```text
HoloViews data model
  Element(data, kdims, vdims)
  Overlay / Layout / HoloMap / DynamicMap
  options and operations
        |
        v
Store registry selects backend-specific Plot class
        |
        v
HoloViews Plot instance
  backend handles
  current plotting state
        |
        v
HoloViews Renderer
        |
        v
Bokeh Models or Matplotlib Artists or Plotly Figure
        |
        v
backend-specific renderer and output
```

Each Element or container maps to a backend-specific Plot class. The
HoloViews Renderer turns Plot state into concrete output. This is documented in
[Plots and Renderers](https://holoviews.org/user_guide/Plots_and_Renderers.html)
and the [Renderer API](https://holoviews.org/reference_manual/holoviews.plotting.renderer.html).

HoloViews uses “Renderer” at a higher layer than Matplotlib. A HoloViews
Renderer coordinates backend Plot objects and export. A Matplotlib Renderer
paints primitive paths and text.

`DynamicMap` and Streams add reactive evaluation around semantic objects. They
can cause new Elements or updated backend state. They are closer to a localized
application dataflow than to a graphical scenegraph.

### Agentic implications

HoloViews gives agents a strong semantic edit target. It also adds a translation
boundary. A visual error can originate in:

```text
Element data or dimensions
options lookup
operation
backend Plot class
backend model or Artist
backend renderer
```

For trace mode, preserve the HoloViews object description and the lowered
backend state. `renderer.get_plot(obj).state` is the key escape hatch. Once an
agent mutates that backend state directly, the mutation is backend-specific and
may not survive a HoloViews refresh.

## 10. Datashader: a rasterization pipeline, not a scenegraph

Datashader deliberately breaks the “one row becomes one retained graphical
item” assumption.

```text
prepared data
     |
Canvas defines pixel grid and coordinate transform
     |
glyph projection into pixels
     |
reduction per pixel
     |
aggregate array
     |
transfer function / shading
     |
raster image
```

The aggregate array is the central intermediate representation. The output can
then become a Bokeh image glyph or another raster surface. See the
[Datashader pipeline](https://datashader.org/getting_started/Pipeline.html).

For agents, preserve the canvas ranges, resolution, reduction, aggregate, and
transfer function. Inspecting a scenegraph cannot explain a wrong pixel when no
per-row scene items exist.

## 11. Perspective: query and viewer state before graphical state

Perspective's public architecture ends at a plugin boundary.

```text
Arrow or prepared rows
        |
        v
Table
  typed columns, updates, immutable schema
        |
        v
View
  selected columns, filters, sorts, pivots, expressions
        |
        v
perspective-viewer
  ViewerConfig, panels, selection, theme
        |
        v
plugin.draw(view) / update(view) / resize(view) / restyle()
        |
        v
plugin-owned DOM, Canvas, WebGL, or other output
```

`Table` is the updateable typed store. `View` is a query projection. The viewer
owns user-facing configuration and plugin lifecycle. A plugin owns the final
graphics implementation.

The viewer can save and restore its configuration. A plugin can save its own
state, but restore is state transfer rather than a drawing request. The host
controls draw and update sequencing. See the
[Perspective viewer API](https://perspective-dev.github.io/viewer/classes/dist_wasm_perspective-viewer.d.ts.PerspectiveViewerElement.html),
[save and restore](https://perspective-dev.github.io/guide/how_to/javascript/save_restore.html),
and the [plugin interface](https://perspective-dev.github.io/viewer/interfaces/dist_esm_plugin.d.ts.IPerspectiveViewerPlugin.html).

Perspective therefore has no universal chart scenegraph for an agent to edit.
The stable agent targets are table schema, View configuration, ViewerConfig,
selection, and the chosen plugin's public state.

## 12. Terms that look equivalent but are not

| Term | System | Architectural meaning |
|---|---|---|
| Artist | Matplotlib | Retained graphical object that participates in drawing |
| Mark definition | Vega | Declarative generator and encoder for a set of scenegraph items |
| Mark item | Vega | Concrete scenegraph instance with resolved visual properties |
| Mark | Observable Plot | JavaScript object that lowers data and channels into DOM output |
| Glyph | Bokeh | Serializable visual-property Model |
| GlyphRenderer | Bokeh | Model linking source, glyph, selection, and visual layer behavior |
| Trace | Plotly | Typed figure-protocol layer that can generate many graphical items |
| Element | HoloViews | Semantic data and dimension object, independent of a backend |
| Plugin | Perspective | Viewer-controlled renderer for a Perspective View |
| Signal | Vega | Named reactive value inside the Vega dataflow runtime |
| Cell or variable | Observable | Node in a notebook or module dependency graph |
| Stream | HoloViews | Event or parameter source that drives dynamic evaluation |
| Property change | Bokeh | Event on a serializable Model, optionally synchronized |
| Relayout or restyle event | Plotly | Browser event and figure patch description |

## 13. “Renderer” crosswalk

| System | What “renderer” means |
|---|---|
| Matplotlib | Low-level backend object that paints paths, text, and images onto a canvas |
| Vega | SVG or Canvas output backend driven by a Vega View and scenegraph |
| Bokeh | `GlyphRenderer` is a retained visual-layer Model; BokehJS Views perform browser drawing |
| Plotly Python | A display target or host policy; Plotly.js owns graphical rendering |
| HoloViews | Backend coordinator and exporter that realizes semantic objects through Plot classes |
| Observable runtime | Inspector displays returned values; a chart library still creates the graphic |
| Browser | Native SVG, Canvas, and WebGL engines finally produce pixels |

## 14. One prepared-data interaction across systems

Assume domain code owns these two records:

```text
PreparedPoints
  row_id, x, y, series_id, color_rgba, marker, tooltip

SemanticViewState
  x_domain, y_domain, selected_row_ids, hovered_row_id
```

The adapters differ:

```text
Matplotlib
  PreparedPoints -> PathCollection offsets and colors
  SemanticViewState -> Axes limits and Artist style mutation

Vega
  PreparedPoints -> named data set
  SemanticViewState -> externally set signals or named state data
  signals -> encoders -> scenegraph items

Observable + Plot
  PreparedPoints and SemanticViewState -> reactive cell inputs
  dependent chart cell rebuilds a Plot-generated SVG

D3
  PreparedPoints -> keyed DOM data join or Canvas redraw loop
  SemanticViewState -> attributes, styles, or drawing commands

Bokeh
  PreparedPoints -> ColumnDataSource
  SemanticViewState -> Range1d and Selection Models
  shared Model identity links views

Plotly
  PreparedPoints -> trace arrays and customdata
  SemanticViewState -> layout range and selectedpoints patches
  Plotly events translate back to semantic row IDs

HoloViews
  PreparedPoints -> Element with dimensions
  SemanticViewState -> Streams or explicit adapter parameters
  Renderer lowers to backend state

Perspective
  PreparedPoints -> Table
  SemanticViewState -> viewer selection and ViewerConfig adapter
  plugin owns final graphical state
```

This semantic state must belong to the report or application. Do not make a
Bokeh selection, Vega signal, Plotly event payload, or Perspective config the
cross-library authority. Each is an adapter representation.

## 15. What an agent should edit, inspect, and avoid

| System | Stable edit target | Runtime inspection | Avoid as durable source |
|---|---|---|---|
| Matplotlib | Figure, Axes, named Artists | Artist hierarchy, transforms, renderer output | backend-private caches |
| Vega | Vega spec and named state | `view.signal`, `view.data`, `getState`, scenegraph | `view._runtime` and direct scene-item mutation |
| Vega-Lite / Altair | Vega-Lite spec or Altair source | compiled Vega plus Vega View | editing compiled Vega by accident |
| Observable runtime | cell/module source | cell values and observers | implicit cross-cell mutable objects |
| D3 SVG | source plus keyed join | DOM, bound `__data__`, events | DOM generated from unstable selectors as source |
| D3 Canvas | redraw code and explicit state | structured trace plus pixels | assuming pixels retain data identity |
| Observable Plot | Plot options and Mark objects | returned DOM and scales | treating DOM as the authoring spec |
| Bokeh | Document Models with names or tags | Model selection, properties, JSON, browser events | BokehJS View internals and Canvas state |
| Plotly | figure JSON and schema paths | events, trace arrays, layout, DOM for diagnosis | private calculated state |
| HoloViews | Elements, containers, options, operations | Plot instance and backend `state` | backend mutations expected to survive refresh |
| Datashader | canvas, glyph, reduction, transfer function | aggregate array and image | per-row graphical identity |
| Perspective | schema, ViewConfig, ViewerConfig, plugin config | `save`, `getView`, selection, render stats | plugin internals as universal state |

## 16. The executable learning sequence

The next walkthrough should use the same prepared points and semantic state.
Each system must complete these labs without chart-owned aggregation:

1. Construct points, a line, text, and an annotation.
2. Print or serialize the authored intermediate representation.
3. Inspect the runtime graph or explain why no public one exists.
4. Inspect the graphical scene or explain which surface replaces it.
5. Change the x-domain without changing prepared data.
6. Select stable `row_id` values and link a second view.
7. Save state, recreate the view, and verify the same result.
8. Publish without Python and list the remaining browser runtime.

The best order is:

```text
Matplotlib reference
        |
        v
Vega: explicit specification + dataflow + scenegraph
        |
        v
Bokeh: serializable model graph + browser Views
        |
        v
Observable runtime, D3, and Plot: host graph versus DOM graphics
        |
        v
Plotly: public figure protocol + private renderer pipeline
        |
        v
HoloViews lowering and Datashader rasterization
        |
        v
Perspective: query/viewer/plugin boundary case
```

The evaluation should score traceability across layers, not code length or
automatic chart construction.
