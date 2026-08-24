# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
#   kernelspec:
#     display_name: Python (charting API philosophy)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # From API to pixels
#
# ## An executable architecture guide for experienced chart authors
#
# A chart API is only the first layer. This report follows prepared data through
# semantic objects, reactive state, graphical scenes, renderers, and browser
# surfaces. Matplotlib's object-oriented API is the reference. Vega, Observable,
# D3, Plot, Bokeh, Plotly, HoloViews, Datashader, and Perspective then expose
# different parts of the same general path.
#
# This is not a chart catalog or a winner ranking. It is a set of interactive
# lowering traces for humans and agents.

# %%
from __future__ import annotations

from collections import Counter
import hashlib
import html
import importlib.metadata as metadata
import json
import time
import warnings
from pathlib import Path

import altair as alt
import bokeh
import datashader as ds
import datashader.transfer_functions as tf
import holoviews as hv
import matplotlib
import numpy as np
import pandas as pd
import plotly
import plotly.graph_objects as go
import pyarrow as pa
import pyarrow.ipc as pa_ipc
import vl_convert as vlc
from bokeh.embed import file_html, json_item
from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, CustomJS, Div, HoverTool, Span
from bokeh.plotting import figure
from bokeh.resources import CDN, INLINE
from IPython.display import HTML, IFrame, clear_output, display
from IPython.utils.capture import capture_output
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from perspective import Server

warnings.filterwarnings(
    "ignore",
    message="Consider using IPython.display.IFrame instead",
    category=UserWarning,
    module="IPython.core.display",
)

ARTIFACTS = Path("artifacts")
DATA = Path("data")
EVIDENCE = Path("evidence")
for directory in (ARTIFACTS, DATA, EVIDENCE):
    directory.mkdir(parents=True, exist_ok=True)

SEED = 20_260_823
ROW_COUNT = 2_400
SERVICES = ["api", "search", "auth", "checkout"]
REGIONS = ["amer", "emea", "apac"]
PALETTE = {
    "api": "#2764ae",
    "search": "#7656a6",
    "auth": "#0d7c76",
    "checkout": "#c35c22",
}

package_versions = {
    label: metadata.version(distribution)
    for label, distribution in {
        "Matplotlib": "matplotlib",
        "Altair": "altair",
        "Vega compiler": "vl-convert-python",
        "Bokeh": "bokeh",
        "Plotly": "plotly",
        "Perspective": "perspective-python",
        "HoloViews": "holoviews",
        "Datashader": "datashader",
        "PyArrow": "pyarrow",
        "pandas": "pandas",
        "NumPy": "numpy",
    }.items()
}
package_versions["Python"] = __import__("platform").python_version()
browser_versions = {
    "Observable Runtime": "6.0.0",
    "Observable Inspector": "5.0.1",
    "Observable Plot": "0.6.17",
    "D3": "7.9.0",
    "AG Grid Community": "36.1.0",
    "Apache Arrow JS": "21.2.0",
    "Perspective browser": "5.2.0",
}


def cards(items: list[tuple[str, str, str]], css_class: str = "trace-grid") -> HTML:
    body = []
    for label, value, note in items:
        body.append(
            "<div class='trace-card'><dl>"
            f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
            f"<dt>{html.escape(note)}</dt>"
            "</dl></div>"
        )
    return HTML(f"<div class='{css_class}'>" + "".join(body) + "</div>")


def iframe(path: Path, height: int = 540) -> IFrame:
    return IFrame(src=path.as_posix(), width="100%", height=height)


def browser_data_resolver_js(relative_path: str) -> str:
    encoded_path = json.dumps(relative_path)
    return f"""
function resolveReportFile(relative) {{
  const host = new URL(window.location.href);
  const labIndex = host.pathname.indexOf("/lab/");
  const treeIndex = host.pathname.lastIndexOf("/tree/");
  if (labIndex >= 0 && treeIndex > labIndex) {{
    const prefix = host.pathname.slice(0, labIndex);
    const notebookPath = host.pathname.slice(treeIndex + "/tree/".length);
    const directory = notebookPath.slice(0, notebookPath.lastIndexOf("/") + 1);
    return host.origin + prefix + "/files/" + directory + relative;
  }}
  const notebooksIndex = host.pathname.indexOf("/notebooks/");
  if (notebooksIndex >= 0) {{
    const prefix = host.pathname.slice(0, notebooksIndex);
    const notebookPath = host.pathname.slice(
      notebooksIndex + "/notebooks/".length
    );
    const directory = notebookPath.slice(0, notebookPath.lastIndexOf("/") + 1);
    return host.origin + prefix + "/files/" + directory + relative;
  }}
  if (host.pathname.includes("/artifacts/")) {{
    return new URL("../" + relative, host).href;
  }}
  return new URL(relative, host).href;
}}
const dataUrl = resolveReportFile({encoded_path});
window.MARKOUT_DATA_URL = dataUrl;
function loadSharedReportBuffer(url) {{
  window.__REPORT_ARRAY_BUFFERS__ ??= new Map();
  if (!window.__REPORT_ARRAY_BUFFERS__.has(url)) {{
    const pending = fetch(url, {{cache: "no-store"}}).then(response => {{
      if (!response.ok) throw new Error("Arrow fetch HTTP " + response.status);
      return response.arrayBuffer();
    }});
    window.__REPORT_ARRAY_BUFFERS__.set(url, pending);
  }}
  return window.__REPORT_ARRAY_BUFFERS__.get(url);
}}
"""


def bounded_json(value: object, *, limit: int = 3_500) -> HTML:
    text = json.dumps(value, indent=2, sort_keys=True, default=str)
    if len(text) > limit:
        text = text[:limit] + "\n… bounded here; full records are in evidence/"
    return HTML(f"<pre><code>{html.escape(text)}</code></pre>")


def byte_label(value: int) -> str:
    if value < 1_024:
        return f"{value:,} B"
    if value < 1_024**2:
        return f"{value / 1_024:.1f} KiB"
    return f"{value / 1_024**2:.2f} MiB"


def standalone_bokeh_html(
    model: object,
    title: str,
    resources: object = INLINE,
) -> str:
    """Return inline Bokeh HTML without an unused Panel ESM shim."""
    rendered = file_html(model, resources, title)
    return "\n".join(
        line
        for line in rendered.splitlines()
        if "static/extensions/panel/bundled/reactiveesm/es-module-shims" not in line
    )


def layer_path(items: list[tuple[str, str]]) -> HTML:
    nodes = "".join(
        f"<div class='flow-node'><strong>{html.escape(label)}</strong>"
        f"<span>{html.escape(note)}</span></div>"
        + ("<div class='flow-arrow'>→</div>" if index < len(items) - 1 else "")
        for index, (label, note) in enumerate(items)
    )
    return HTML(f"<div class='flow-strip'>{nodes}</div>")


clear_output(wait=True)
display(
    HTML(
        """
<div class="report-hero">
  <div>
    <div class="hero-kicker">Executable architecture guide</div>
    <h2>A chart is the last visible state of several different machines.</h2>
    <p>The useful question is not only “which API call?” It is “which layer
    owns meaning, dependency, geometry, state, and pixels?”</p>
  </div>
  <div class="hero-grid">
    <div class="hero-stat"><strong>7 layers</strong><span>one neutral model</span></div>
    <div class="hero-stat"><strong>12 systems</strong><span>distinct boundaries</span></div>
    <div class="hero-stat"><strong>4 verbs</strong><span>edit · lower · inspect · verify</span></div>
    <div class="hero-stat"><strong>0 rankings</strong><span>architecture before preference</span></div>
  </div>
</div>
"""
    )
)

# %% [markdown]
# ## 1. Keep seven layers in your head
#
# The same word often names different things across libraries. Start with a
# neutral model, then map each library into it:
#
# 1. **Authoring API**: the code or specification that you edit.
# 2. **Semantic IR**: retained visual intent before final geometry.
# 3. **Reactive or dataflow graph**: dependencies that recompute.
# 4. **Graphical scene**: concrete retained graphical objects.
# 5. **Renderer**: code that converts graphical state to output.
# 6. **Output surface**: SVG, Canvas, WebGL, bitmap, or vector file.
# 7. **Host graph**: state outside the chart, such as Observable cells or
#    Jupyter widgets.
#
# Coordinate lowering and interaction state can cross several of these layers.
# Not every system exposes every layer. That is an architectural property.

# %%
display(
    layer_path(
        [
            ("authoring API", "what you edit"),
            ("semantic IR", "visual intent"),
            ("reactive graph", "what recomputes"),
            ("graphical scene", "retained items"),
            ("renderer", "draw operation"),
            ("output", "SVG · Canvas · pixels"),
        ]
    )
)
display(
    HTML(
        """
<div class="method-card">
  <span class="evidence-tag" data-kind="documented">two graph warning</span>
  <p>A dependency graph and a graphical scene are not the same graph. Vega
  exposes both. Observable cells belong to a surrounding dependency graph.
  Matplotlib mainly exposes a retained Artist hierarchy.</p>
</div>
"""
    )
)

vocabulary = pd.DataFrame(
    [
        ("semantic instruction", "Vega-Lite mark", "not yet one screen object"),
        ("mark definition", "Vega mark", "generates and encodes mark items"),
        ("mark item", "Vega scenegraph item", "resolved graphical instance"),
        ("reactive scalar", "Vega signal", "inside one Vega View"),
        ("reactive variable", "Observable cell", "node in a host module graph"),
        ("retained object", "Matplotlib Artist", "Python graphical hierarchy"),
        ("model", "Bokeh Model", "serializable application graph node"),
        ("mark", "Observable Plot Mark", "JavaScript object that produces DOM"),
        ("plugin", "Perspective plugin", "renderer behind a viewer boundary"),
    ],
    columns=["neutral role", "library term", "do not confuse with"],
)
display(HTML(vocabulary.to_html(index=False, classes="compact-table", border=0)))

# %% [markdown]
# ## 2. Prepare analytical meaning before chart authoring
#
# This report does not compare chart-owned aggregation. A deterministic table
# supplies rows. A separate preparation step supplies the p95 reference and
# service summary. In normal work, Polars or SQL can own this step.
#
# The chart runtimes may filter rows for interaction. That is view state, not
# the source of analytical truth.

# %%
rng = np.random.default_rng(SEED)
service = rng.choice(SERVICES, size=ROW_COUNT, p=[0.38, 0.25, 0.19, 0.18])
region = rng.choice(REGIONS, size=ROW_COUNT, p=[0.46, 0.30, 0.24])
minute = rng.uniform(0, 60, size=ROW_COUNT)
payload_kb = rng.lognormal(mean=2.0, sigma=0.72, size=ROW_COUNT)

service_base = pd.Series(service).map(
    {"api": 72, "search": 112, "auth": 58, "checkout": 138}
).to_numpy()
region_penalty = pd.Series(region).map(
    {"amer": 0, "emea": 18, "apac": 34}
).to_numpy()
incident = (
    (minute >= 22)
    & (minute <= 29)
    & np.isin(service, ["search", "checkout"])
)
latency_ms = (
    service_base
    + region_penalty
    + 3.1 * payload_kb
    + rng.gamma(shape=2.0, scale=15.0, size=ROW_COUNT)
    + incident * rng.gamma(shape=4.5, scale=42.0, size=ROW_COUNT)
)
error_probability = np.clip(0.008 + latency_ms / 8_000 + incident * 0.10, 0, 0.42)
error = rng.random(ROW_COUNT) < error_probability

requests = pd.DataFrame(
    {
        "request_id": np.arange(1, ROW_COUNT + 1),
        "service": pd.Categorical(service, categories=SERVICES, ordered=True),
        "region": pd.Categorical(region, categories=REGIONS, ordered=True),
        "minute": minute.round(3),
        "payload_kb": payload_kb.round(3),
        "latency_ms": latency_ms.round(3),
        "error": error,
    }
).sort_values("request_id", ignore_index=True)

data_path = DATA / "requests.csv"
requests.to_csv(data_path, index=False, lineterminator="\n")
data_sha256 = hashlib.sha256(data_path.read_bytes()).hexdigest()
p95_latency = float(requests["latency_ms"].quantile(0.95))
service_summary = (
    requests.groupby("service", observed=True)
    .agg(
        requests=("request_id", "size"),
        mean_latency_ms=("latency_ms", "mean"),
        p95_latency_ms=("latency_ms", lambda values: values.quantile(0.95)),
        errors=("error", "sum"),
    )
    .reset_index()
)

assert len(requests) == ROW_COUNT
assert int(service_summary["requests"].sum()) == ROW_COUNT
assert not requests.isna().any().any()
assert np.isclose(p95_latency, np.quantile(requests["latency_ms"], 0.95))

display(
    cards(
        [
            ("prepared rows", f"{len(requests):,}", "one source table"),
            ("p95 latency", f"{p95_latency:.1f} ms", "prepared outside charts"),
            ("errors", f"{int(requests['error'].sum()):,}", "prepared field"),
            ("data SHA-256", data_sha256[:16] + "…", "replay identity"),
        ]
    )
)
display(service_summary.round(2).style.hide(axis="index"))

# %% [markdown]
# ## 3. Matplotlib OO is the retained-object reference
#
# The object path is direct: create a 'Figure', obtain an 'Axes', add Artists,
# then ask a backend renderer to draw them. The public hierarchy remains live
# Python state. A 'PathCollection' represents many points; one row does not
# become one top-level Artist.
#
# Matplotlib documents 'FigureCanvas', 'Renderer', and 'Artist' as its core
# architecture ([Artist tutorial](https://matplotlib.org/stable/tutorials/artists.html)).
# The report does not use pyplot state as an authoring interface.

# %%
matplotlib_start = time.perf_counter()
fig_mpl = Figure(figsize=(11.2, 5.8), constrained_layout=True)
FigureCanvasAgg(fig_mpl)
ax_mpl = fig_mpl.subplots()
for name in SERVICES:
    frame = requests.loc[requests["service"] == name]
    ax_mpl.scatter(
        frame["payload_kb"],
        frame["latency_ms"],
        s=16,
        alpha=0.46,
        color=PALETTE[name],
        label=name,
        edgecolors="none",
    )
ax_mpl.axhline(p95_latency, color="#b8423e", linestyle="--", linewidth=1.4)
ax_mpl.text(
    requests["payload_kb"].quantile(0.93),
    p95_latency + 12,
    f"prepared p95 {p95_latency:.0f} ms",
    color="#b8423e",
    fontsize=9,
)
ax_mpl.set(
    xlabel="payload (KiB)",
    ylabel="latency (ms)",
    title="Matplotlib OO: mutate a retained Artist hierarchy",
)
ax_mpl.set_xscale("log")
ax_mpl.grid(alpha=0.15)
ax_mpl.legend(frameon=False, ncols=4, loc="upper center")
fig_mpl.canvas.draw()
matplotlib_build_ms = (time.perf_counter() - matplotlib_start) * 1_000

artist_counts = Counter(type(artist).__name__ for artist in fig_mpl.findobj())
mpl_trace = {
    "authoring_root": type(fig_mpl).__name__,
    "axes": len(fig_mpl.axes),
    "artist_count": sum(artist_counts.values()),
    "artist_types": dict(artist_counts.most_common(12)),
    "renderer": type(fig_mpl.canvas.get_renderer()).__name__,
    "backend": matplotlib.get_backend(),
}
display(fig_mpl)
display(
    cards(
        [
            ("authoring root", "Figure", "public retained object"),
            ("point containers", str(len(ax_mpl.collections)), "PathCollection objects"),
            ("Artists found", str(mpl_trace["artist_count"]), "recursive public inspection"),
            ("renderer", mpl_trace["renderer"], "Agg draw target"),
        ]
    )
)
display(bounded_json(mpl_trace))

# %% [markdown]
# ### Where Seaborn now fits
#
# Seaborn is useful as a statistical example corpus and a concise constructor
# over Matplotlib. It does not add a new renderer. Its axes-level functions
# create or modify Matplotlib Artists; its figure-level functions own a
# figure-like grid ([function overview](https://seaborn.pydata.org/tutorial/function_overview.html)).
#
# Because this report prepares analytical meaning first, Seaborn is not a
# primary architecture lab. An agent can still use its examples to identify a
# sound statistical display, then implement or refine that display through the
# Matplotlib object model.

# %% [markdown]
# ## 4. Bokeh model graph versus Plotly figure protocol
#
# Both systems cross from Python into JavaScript, but their public retained
# objects differ.
#
# Bokeh serializes a graph of Models. Shared object identity is meaningful:
# two glyph renderers can reference one 'ColumnDataSource', and one selection
# then affects both views. Plotly publishes a figure protocol with stable
# 'data', 'layout', and 'frames' roots. Plotly.js owns the rendering runtime
# below that protocol
# ([Bokeh models](https://docs.bokeh.org/en/latest/docs/user_guide/basic/data.html),
# [Plotly figure structure](https://plotly.com/python/figure-structure/)).

# %%
bokeh_start = time.perf_counter()
bokeh_frame = requests.assign(
    service=requests["service"].astype(str),
    region=requests["region"].astype(str),
)
bokeh_frame["color"] = bokeh_frame["service"].map(PALETTE)
source_bokeh = ColumnDataSource(bokeh_frame, name="shared_requests")
selection_status = Div(
    text=f"<b>Shared selection:</b> 0 of {ROW_COUNT:,} rows",
    name="selection_status",
    width=1220,
    styles={"padding": "8px", "background": "#f6f3ec", "border-radius": "8px"},
)
source_bokeh.selected.js_on_change(
    "indices",
    CustomJS(
        args={"status": selection_status, "total": ROW_COUNT},
        code="""
status.text = "<b>Shared selection:</b> "
  + cb_obj.indices.length.toLocaleString() + " of "
  + total.toLocaleString() + " rows · one Selection model";
""",
    ),
)

plot_payload = figure(
    width=600,
    height=420,
    x_axis_type="log",
    title="Select rows: one Model changes",
    tools="pan,wheel_zoom,box_select,lasso_select,reset",
    active_drag="box_select",
)
points_payload = plot_payload.scatter(
    x="payload_kb",
    y="latency_ms",
    source=source_bokeh,
    color="color",
    size=5,
    alpha=0.48,
    selection_alpha=0.95,
    nonselection_alpha=0.05,
)
plot_payload.add_tools(
    HoverTool(
        renderers=[points_payload],
        tooltips=[
            ("service", "@service"),
            ("region", "@region"),
            ("payload", "@payload_kb{0.0} KiB"),
            ("latency", "@latency_ms{0.0} ms"),
        ],
    )
)
plot_payload.add_layout(
    Span(
        location=p95_latency,
        dimension="width",
        line_color="#b8423e",
        line_dash="dashed",
    )
)
plot_payload.xaxis.axis_label = "payload (KiB)"
plot_payload.yaxis.axis_label = "latency (ms)"

plot_time = figure(
    width=600,
    height=420,
    title="The second renderer reads the same selection",
    tools="pan,wheel_zoom,box_select,lasso_select,reset",
    active_drag="box_select",
    y_range=plot_payload.y_range,
)
plot_time.scatter(
    x="minute",
    y="latency_ms",
    source=source_bokeh,
    color="color",
    size=5,
    alpha=0.48,
    selection_alpha=0.95,
    nonselection_alpha=0.05,
)
plot_time.xaxis.axis_label = "minute"
plot_time.yaxis.axis_label = "latency (ms)"
bokeh_layout = column(selection_status, row(plot_payload, plot_time))

bokeh_models = list(bokeh_layout.references())
bokeh_model_types = Counter(type(model).__name__ for model in bokeh_models)
bokeh_item = json_item(bokeh_layout)
bokeh_json = json.dumps(bokeh_item, default=str, separators=(",", ":"))
bokeh_path = ARTIFACTS / "bokeh-model-graph.html"
bokeh_path.write_text(
    standalone_bokeh_html(bokeh_layout, "Bokeh model graph"),
    encoding="utf-8",
)
bokeh_build_ms = (time.perf_counter() - bokeh_start) * 1_000
bokeh_trace = {
    "model_count": len(bokeh_models),
    "model_types": dict(bokeh_model_types.most_common(16)),
    "shared_source_id": source_bokeh.id,
    "selection_model_id": source_bokeh.selected.id,
    "json_bytes": len(bokeh_json),
}
display(
    layer_path(
        [
            ("Python models", "Figure · glyph · source"),
            ("Document graph", "IDs + references"),
            ("BokehJS views", "browser counterparts"),
            ("Canvas", "interactive output"),
        ]
    )
)
display(iframe(bokeh_path, height=520))
display(
    cards(
        [
            ("Models", str(len(bokeh_models)), "public graph references"),
            ("shared source", source_bokeh.id, "one identity"),
            ("selection", source_bokeh.selected.id, "linked state owner"),
            ("serialized graph", f"{len(bokeh_json):,} bytes", "derived document"),
        ]
    )
)
display(bounded_json(bokeh_trace))

# %%
plotly_start = time.perf_counter()
figure_plotly = go.Figure()
for name in SERVICES:
    frame = requests.loc[requests["service"] == name]
    figure_plotly.add_trace(
        go.Scattergl(
            x=frame["payload_kb"],
            y=frame["latency_ms"],
            mode="markers",
            name=name,
            customdata=np.column_stack(
                [
                    frame["request_id"],
                    frame["region"].astype(str),
                    frame["error"],
                ]
            ),
            marker={"color": PALETTE[name], "size": 6, "opacity": 0.55},
            hovertemplate=(
                "request %{customdata[0]}<br>region %{customdata[1]}"
                "<br>payload %{x:.1f} KiB<br>latency %{y:.1f} ms"
                "<br>error %{customdata[2]}<extra>" + name + "</extra>"
            ),
        )
    )
figure_plotly.add_hline(
    y=p95_latency,
    line_dash="dash",
    line_color="#b8423e",
    annotation_text=f"prepared p95 {p95_latency:.0f} ms",
)
figure_plotly.update_layout(
    title="Plotly graph_objects.Figure → Plotly.js",
    template="plotly_white",
    height=510,
    xaxis={"type": "log", "title": "payload (KiB)"},
    yaxis={"title": "latency (ms)"},
    legend={"orientation": "h"},
    margin={"l": 55, "r": 30, "t": 80, "b": 45},
)
plotly_json = figure_plotly.to_json()
plotly_path = ARTIFACTS / "plotly-figure-protocol.html"
figure_plotly.write_html(plotly_path, include_plotlyjs="cdn", full_html=True)
plotly_html = plotly_path.read_text(encoding="utf-8")
plotly_html = plotly_html.replace(
    "</body>",
    """<style>
#plotly-event{font:12px ui-monospace,monospace;white-space:pre-wrap;background:#f6f3ec;
border:1px solid #d9d3c6;border-radius:10px;padding:10px;margin:10px}
</style>
<pre id="plotly-event">Click a point or change the range to inspect a Plotly.js event payload.</pre>
<script>
const plot = document.querySelector('.plotly-graph-div');
const panel = document.querySelector('#plotly-event');
const show = (kind, payload) => {
  const bounded = kind === 'plotly_click'
    ? {curveNumber:payload.points[0].curveNumber, pointNumber:payload.points[0].pointNumber,
       x:payload.points[0].x, y:payload.points[0].y}
    : payload;
  panel.textContent = JSON.stringify({event:kind, payload:bounded}, null, 2);
};
plot.on('plotly_click', payload => show('plotly_click', payload));
plot.on('plotly_relayout', payload => show('plotly_relayout', payload));
window.PLOTLY_LAB = {plot, figureRoots:['data','layout','frames']};
</script></body>""",
)
plotly_path.write_text(plotly_html, encoding="utf-8")
plotly_build_ms = (time.perf_counter() - plotly_start) * 1_000
plotly_outline = {
    "public_roots": list(figure_plotly.to_dict()),
    "trace_count": len(figure_plotly.data),
    "trace_types": sorted({trace.type for trace in figure_plotly.data}),
    "layout_keys": sorted(figure_plotly.layout.to_plotly_json()),
    "figure_json_bytes": len(plotly_json),
}
display(
    layer_path(
        [
            ("graph_objects", "Python constructors"),
            ("Figure", "data · layout · frames"),
            ("Plotly.js", "private rendering runtime"),
            ("WebGL", "Scattergl surface"),
        ]
    )
)
display(iframe(plotly_path, height=650))
display(
    cards(
        [
            ("public roots", "data · layout · frames", "figure protocol"),
            ("traces", str(len(figure_plotly.data)), "four prepared groups"),
            ("renderer trace", "Scattergl", "WebGL-backed marks"),
            ("figure JSON", f"{len(plotly_json):,} bytes", "serializable state"),
        ]
    )
)
display(bounded_json(plotly_outline))

# %% [markdown]
# ### Why these graphs are not equivalent
#
# In Bokeh, model identity and references are part of the public application
# model. In Plotly, the public contract is the figure tree and event protocol;
# the rendering scene below Plotly.js is not a stable authoring surface.
#
# Edit Bokeh models when linked object identity is the design. Edit the Plotly
# figure when a portable figure protocol is the design. In both cases, keep a
# semantic selection outside renderer-specific event payloads when several
# systems must link.

# %% [markdown]
# ## 5. Altair and Vega-Lite compile into Vega
#
# Altair is a typed Python constructor for Vega-Lite. Vega-Lite is a semantic
# JSON language. The Vega-Lite compiler expands it into Vega, which exposes data
# operators, signals, scales, mark definitions, and a scenegraph
# ([Vega-Lite compilation](https://vega.github.io/vega-lite/usage/compile.html),
# [Vega View API](https://vega.github.io/vega/docs/api/view/)).
#
# A Vega-Lite point mark is not one final graphical object. A Vega mark
# definition can generate many scenegraph mark items. A Vega signal is a
# reactive value inside one Vega View, not an Observable notebook cell.

# %%
altair_start = time.perf_counter()
service_select = alt.selection_point(name="service_pick", fields=["service"])
points_alt = (
    alt.Chart(requests)
    .mark_circle(size=38)
    .encode(
        x=alt.X(
            "payload_kb:Q",
            scale=alt.Scale(type="log"),
            title="payload (KiB)",
        ),
        y=alt.Y("latency_ms:Q", title="latency (ms)"),
        color=alt.Color(
            "service:N",
            sort=SERVICES,
            scale=alt.Scale(
                domain=SERVICES,
                range=[PALETTE[name] for name in SERVICES],
            ),
        ),
        opacity=alt.condition(service_select, alt.value(0.72), alt.value(0.10)),
        tooltip=[
            "request_id:Q",
            "service:N",
            "region:N",
            alt.Tooltip("payload_kb:Q", format=".1f"),
            alt.Tooltip("latency_ms:Q", format=".1f"),
            "error:N",
        ],
    )
    .add_params(service_select)
)
rule_alt = (
    alt.Chart(pd.DataFrame({"p95_latency": [p95_latency]}))
    .mark_rule(color="#b8423e", strokeDash=[6, 4])
    .encode(y="p95_latency:Q")
)
chart_alt = (
    (points_alt + rule_alt)
    .properties(
        width=900,
        height=430,
        title="Click a service: Vega signals update the visible scene",
    )
    .configure_view(stroke="#d9d3c6")
    .configure_axis(gridOpacity=0.16)
)
vl_spec = chart_alt.to_dict()
vega_spec = vlc.vegalite_to_vega(vl_spec)
altair_build_ms = (time.perf_counter() - altair_start) * 1_000

vl_json = json.dumps(vl_spec, sort_keys=True, separators=(",", ":"))
vega_json = json.dumps(vega_spec, sort_keys=True, separators=(",", ":"))
altair_path = ARTIFACTS / "vega-runtime.html"
chart_alt.save(altair_path, inline=True)
vega_html = altair_path.read_text(encoding="utf-8")
vega_html = vega_html.replace(
    "<body>",
    """<body>
<style>
body{font-family:system-ui,sans-serif;background:#fffdf8;color:#172126;margin:16px}
#runtime-state{white-space:pre-wrap;background:#f6f3ec;border:1px solid #d9d3c6;
border-radius:10px;padding:10px;max-height:180px;overflow:auto;font-size:12px}
</style>
<h3>Vega View: runtime inspection</h3>
<p>Click a point. The visual update comes from generated Vega signals and dataflow.</p>""",
)
vega_html = vega_html.replace(
    "vegaEmbed('#vis', spec, embedOpt).catch(console.error);",
    """vegaEmbed('#vis', spec, embedOpt).then(result => {
  window.VEGA_LAB = result;
  const countItems = item => {
    if (!item) return 0;
    const children = item.items || [];
    return 1 + children.reduce((total, child) => total + countItems(child), 0);
  };
  const update = () => {
    const panel = document.querySelector('#runtime-state');
    if (!panel) return;
    const state = result.view.getState({
      signals: name => !name.startsWith('_'),
      data: () => false
    });
    panel.textContent = JSON.stringify({
      renderer: result.view.renderer(),
      publicSignals: state.signals,
      sceneItems: countItems(result.view.scenegraph().root)
    }, null, 2);
  };
  result.view.addEventListener('click', () => setTimeout(update, 0));
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', update, {once: true});
  } else {
    update();
  }
}).catch(console.error);""",
)
vega_html = vega_html.replace(
    "</body>",
    "<h4>Public Vega View checkpoint</h4><pre id='runtime-state'>loading…</pre></body>",
)
altair_path.write_text(vega_html, encoding="utf-8")

vega_trace = {
    "altair_output": "Vega-Lite JSON",
    "vega_lite_schema": vl_spec.get("$schema"),
    "vega_schema": vega_spec.get("$schema"),
    "vega_data_sources": [item.get("name") for item in vega_spec.get("data", [])],
    "vega_signal_names": [item.get("name") for item in vega_spec.get("signals", [])],
    "vega_scales": [item.get("name") for item in vega_spec.get("scales", [])],
    "vega_mark_definitions": len(vega_spec.get("marks", [])),
    "vega_lite_bytes": len(vl_json),
    "compiled_vega_bytes": len(vega_json),
}
display(
    layer_path(
        [
            ("Altair", "Python constructors"),
            ("Vega-Lite", "semantic JSON IR"),
            ("Vega", "runtime specification"),
            ("dataflow", "signals + operators"),
            ("scenegraph", "mark items"),
            ("SVG", "browser output"),
        ]
    )
)
display(iframe(altair_path, height=720))
display(
    cards(
        [
            ("Vega-Lite", f"{len(vl_json):,} bytes", "canonical generated spec"),
            ("compiled Vega", f"{len(vega_json):,} bytes", "derived inspection target"),
            ("signals", str(len(vega_spec.get("signals", []))), "runtime variables"),
            ("mark definitions", str(vega_trace["vega_mark_definitions"]), "not mark items"),
        ]
    )
)
display(bounded_json(vega_trace))

# %% [markdown]
# ### The agent boundary
#
# Edit Altair or the Vega-Lite specification. Inspect the compiled Vega and the
# public Vega View when you need a lowering trace. Do not silently edit compiled
# Vega and continue to call Altair the source of truth. A deliberate escape to
# Vega is valid, but it changes the source language.
#
# Vega's public debug surface includes signals, named data, scales, state, and
# the scenegraph. Private runtime operators can help diagnose a failure, but
# they are not a stable authoring API
# ([Vega debugging](https://vega.github.io/vega/docs/api/debugging/)).

# %% [markdown]
# ## 6. Observable, D3, and Plot are three different layers
#
# “Observable” can mean a notebook runtime or Observable Plot. They are not the
# same architecture.
#
# - An **Observable cell** is a variable in a module dependency graph.
# - **D3** usually mutates SVG, Canvas, or DOM nodes through explicit JavaScript.
# - An **Observable Plot mark** is a JavaScript object that lowers data and
#   channels into a returned DOM tree.
#
# A cell can return a Plot chart. That places the Plot DOM inside the Observable
# host graph. The cell does not become a Vega signal, and Plot does not gain a
# Vega scenegraph
# ([Observable Runtime](https://github.com/observablehq/runtime),
# [Plot marks](https://observablehq.com/plot/features/marks),
# [D3 selections](https://d3js.org/d3-selection)).

# %%
observable_rows = requests.assign(
    service=requests["service"].astype(str),
    region=requests["region"].astype(str),
).to_dict(orient="records")
observable_data_json = json.dumps(observable_rows, separators=(",", ":")).replace(
    "</", "<\\/"
)
observable_template = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<style>
body{font-family:system-ui,sans-serif;background:#fffdf8;color:#172126;margin:18px}
button{border:1px solid #d9d3c6;border-radius:999px;background:white;padding:7px 12px;
margin:0 5px 8px 0;cursor:pointer} button.active{background:#172126;color:white}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{border:1px solid #d9d3c6;
border-radius:14px;padding:12px;background:white}.label{color:#c35c22;text-transform:uppercase;
font-size:11px;letter-spacing:.1em;font-weight:700}svg{max-width:100%;height:auto}
pre{background:#f6f3ec;padding:10px;border-radius:10px;white-space:pre-wrap}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style></head><body>
<h2>One host selection, two graphical paths</h2>
<p>The buttons change an Observable variable and also call an explicit D3 update.</p>
<div id="buttons"></div>
<div class="grid">
  <section class="card"><div class="label">Observable cell graph → Plot DOM</div>
    <div id="summary"></div><div id="plot"></div></section>
  <section class="card"><div class="label">Direct D3 mutation → SVG DOM</div>
    <div id="d3"></div><pre id="d3-state"></pre></section>
</div>
<script type="module">
import {Runtime} from "https://cdn.jsdelivr.net/npm/@observablehq/runtime@6.0.0/+esm";
import {Inspector} from "https://cdn.jsdelivr.net/npm/@observablehq/inspector@5.0.1/+esm";
import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.17/+esm";
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";

const rows = __ROWS__;
const services = ["all", "api", "search", "auth", "checkout"];
const colors = {api:"#2764ae",search:"#7656a6",auth:"#0d7c76",checkout:"#c35c22"};
const runtime = new Runtime();
const main = runtime.module();

main.variable().define("selectedService", [], () => "all");
main.variable().define("filtered", ["selectedService"], selected =>
  selected === "all" ? rows : rows.filter(row => row.service === selected)
);
main.variable(new Inspector(document.querySelector("#summary")))
  .define("summary", ["selectedService", "filtered"], (selected, filtered) =>
    selected + " · " + filtered.length.toLocaleString() + " rows · reactive cell value"
  );
main.variable(new Inspector(document.querySelector("#plot")))
  .define("plot", ["filtered"], filtered => Plot.plot({
    width: 600, height: 390, grid: true,
    x: {type:"log", label:"payload (KiB)"},
    y: {label:"latency (ms)"},
    color: {domain:Object.keys(colors), range:Object.values(colors), legend:true},
    marks: [
      Plot.dot(filtered, {x:"payload_kb", y:"latency_ms", fill:"service", r:2.5,
        opacity:.55, tip:true}),
      Plot.ruleY([__P95__], {stroke:"#b8423e", strokeDasharray:"6,4"})
    ]
  }));

const width = 600, height = 390;
const svg = d3.select("#d3").append("svg").attr("viewBox", [0, 0, width, height]);
const x = d3.scaleLog().domain(d3.extent(rows, d => d.payload_kb)).nice().range([52, width-18]);
const y = d3.scaleLinear().domain(d3.extent(rows, d => d.latency_ms)).nice().range([height-40, 18]);
svg.append("g").attr("transform", "translate(0," + (height-40) + ")").call(d3.axisBottom(x));
svg.append("g").attr("transform", "translate(52,0)").call(d3.axisLeft(y));
svg.append("line").attr("x1",52).attr("x2",width-18).attr("y1",y(__P95__))
  .attr("y2",y(__P95__)).attr("stroke","#b8423e").attr("stroke-dasharray","6,4");
const dots = svg.append("g").selectAll("circle").data(rows).join("circle")
  .attr("cx", d => x(d.payload_kb)).attr("cy", d => y(d.latency_ms))
  .attr("r", 2.4).attr("fill", d => colors[d.service]).attr("opacity", .5);

function updateD3(selected) {
  dots.attr("opacity", d => selected === "all" || d.service === selected ? .55 : .035);
  document.querySelector("#d3-state").textContent = JSON.stringify({
    operation: "explicit selection.attr mutation",
    selected,
    retainedCircleNodes: dots.size(),
    visibleRows: selected === "all" ? rows.length : rows.filter(r => r.service === selected).length
  }, null, 2);
}

const buttons = document.querySelector("#buttons");
for (const service of services) {
  const button = document.createElement("button");
  button.textContent = service;
  button.dataset.service = service;
  button.onclick = () => {
    for (const item of buttons.children) item.classList.toggle("active", item === button);
    main.redefine("selectedService", [], () => service);
    updateD3(service);
  };
  buttons.append(button);
}
buttons.firstElementChild.classList.add("active");
updateD3("all");
window.OBSERVABLE_D3_PLOT_LAB = {runtime, main, rows, svg:svg.node()};
</script></body></html>"""
observable_html = (
    observable_template.replace("__ROWS__", observable_data_json)
    .replace("__P95__", f"{p95_latency:.12f}")
)
observable_path = ARTIFACTS / "observable-d3-plot.html"
observable_path.write_text(observable_html, encoding="utf-8")

display(
    layer_path(
        [
            ("host button", "application state"),
            ("Observable cell", "dependency recompute"),
            ("Plot mark", "semantic JS object"),
            ("DOM tree", "returned SVG"),
        ]
    )
)
display(iframe(observable_path, height=690))
display(
    cards(
        [
            ("Observable", "module variables", "host dependency graph"),
            ("D3", f"{ROW_COUNT:,} circles", "explicit DOM mutation"),
            ("Plot", "dot + rule marks", "regenerated SVG DOM"),
            ("shared state", "service name", "semantic host contract"),
        ]
    )
)

# %% [markdown]
# ## 7. HoloViews lowers semantics; Datashader rasterizes aggregates
#
# HoloViews retains domain-oriented Elements and compositions, then a backend
# renderer lowers them into Bokeh, Matplotlib, or Plotly objects. Datashader is
# different: it aggregates rows into a fixed screen-space array, then applies a
# transfer function to make an image
# ([HoloViews plots and renderers](https://holoviews.org/user_guide/Plots_and_Renderers.html),
# [Datashader pipeline](https://datashader.org/getting_started/Pipeline.html)).
#
# Datashader therefore breaks the “one row becomes one retained graphical
# object” model. The aggregate array is its central inspection point.

# %%
holoviz_start = time.perf_counter()
with capture_output():
    hv.extension("bokeh")

service_elements = {}
for name in SERVICES:
    frame = requests.loc[requests["service"] == name]
    service_elements[name] = hv.Points(
        frame,
        kdims=["payload_kb", "latency_ms"],
        vdims=["request_id", "region", "error"],
        label=name,
    ).opts(
        color=PALETTE[name],
        size=4,
        alpha=0.50,
        tools=["hover"],
    )
holoviz_points = hv.NdOverlay(service_elements, kdims="service")
holoviz_view = (
    holoviz_points
    * hv.HLine(p95_latency).opts(
        color="#b8423e",
        line_dash="dashed",
        line_width=1.5,
    )
).opts(
    width=980,
    height=470,
    logx=True,
    xlabel="payload (KiB)",
    ylabel="latency (ms)",
    title="HoloViews semantic objects lowered to Bokeh",
)
holoviz_plot = hv.renderer("bokeh").get_plot(holoviz_view)
resolved_bokeh_model = holoviz_plot.state
holoviz_path = ARTIFACTS / "holoviews-lowering.html"
holoviz_path.write_text(
    standalone_bokeh_html(resolved_bokeh_model, "HoloViews lowering"),
    encoding="utf-8",
)
holoviz_build_ms = (time.perf_counter() - holoviz_start) * 1_000
holoviz_trace = {
    "semantic_root": type(holoviz_view).__name__,
    "semantic_children": [type(item).__name__ for item in holoviz_view.values()],
    "backend": hv.Store.current_backend,
    "resolved_model": type(resolved_bokeh_model).__name__,
    "resolved_model_count": len(resolved_bokeh_model.references()),
    "html_bytes": holoviz_path.stat().st_size,
}
display(
    layer_path(
        [
            ("HoloViews Elements", "Points + HLine"),
            ("Overlay", "semantic composition"),
            ("backend renderer", "Bokeh lowering"),
            ("Bokeh models", "resolved graph"),
            ("Canvas", "browser output"),
        ]
    )
)
display(iframe(holoviz_path, height=545))
display(
    cards(
        [
            ("semantic root", holoviz_trace["semantic_root"], "HoloViews composition"),
            ("backend", holoviz_trace["backend"], "selected later"),
            ("resolved root", holoviz_trace["resolved_model"], "Bokeh model"),
            ("resolved models", str(holoviz_trace["resolved_model_count"]), "lowering trace"),
        ]
    )
)
display(bounded_json(holoviz_trace))

# %%
datashader_start = time.perf_counter()
canvas = ds.Canvas(
    plot_width=900,
    plot_height=430,
    x_range=(
        float(requests["payload_kb"].min()),
        float(requests["payload_kb"].max()),
    ),
    y_range=(
        float(requests["latency_ms"].min()),
        float(requests["latency_ms"].max()),
    ),
    x_axis_type="log",
)
ds_frame = requests.assign(service=requests["service"].astype("category"))
aggregate = canvas.points(
    ds_frame,
    "payload_kb",
    "latency_ms",
    agg=ds.count_cat("service"),
)
shaded = tf.set_background(
    tf.shade(aggregate, color_key=PALETTE, how="eq_hist"),
    "white",
)
datashader_build_ms = (time.perf_counter() - datashader_start) * 1_000
datashader_trace = {
    "input_rows": len(ds_frame),
    "aggregate_shape": list(aggregate.shape),
    "aggregate_dims": list(aggregate.dims),
    "nonzero_bins": int((aggregate.sum(dim="service").values > 0).sum()),
    "max_rows_in_bin": int(aggregate.sum(dim="service").max().item()),
    "output_type": type(shaded).__name__,
}
display(shaded.to_pil())
display(
    layer_path(
        [
            ("prepared rows", f"{ROW_COUNT:,} records"),
            ("Canvas glyph", "point binning"),
            ("aggregate", "430 × 900 × service"),
            ("transfer function", "shade + background"),
            ("bitmap", "one raster"),
        ]
    )
)
display(
    cards(
        [
            ("input rows", f"{ROW_COUNT:,}", "prepared records"),
            ("aggregate cells", f"{aggregate.shape[0] * aggregate.shape[1]:,}", "screen grid"),
            ("nonzero bins", f"{datashader_trace['nonzero_bins']:,}", "inspectable aggregate"),
            ("output", datashader_trace["output_type"], "raster, not scenegraph"),
        ]
    )
)
display(bounded_json(datashader_trace))

# %% [markdown]
# ### The HoloViz split that matters
#
# HoloViews keeps semantic objects that can lower through different backends.
# Datashader keeps an aggregate and image pipeline. Panel can add a host
# application graph, but a dynamic Panel or Datashader interaction can require
# live Python. The static artifacts here preserve only browser-side Bokeh
# interaction and one computed raster.

# %% [markdown]
# ## 8. Perspective ends at a viewer and plugin boundary
#
# Perspective is not a universal chart scenegraph. A 'Table' owns typed data,
# a 'View' owns query state, a viewer owns saved presentation state, and a
# plugin renders the current View. Different plugins can use different internal
# graphical systems
# ([viewer API](https://perspective-dev.github.io/viewer/classes/dist_wasm_perspective-viewer.d.ts.PerspectiveViewerElement.html),
# [plugin interface](https://perspective-dev.github.io/viewer/interfaces/dist_esm_plugin.d.ts.IPerspectiveViewerPlugin.html)).
#
# This lab loads prepared rows without a chart-owned group-by. Sorting and
# visible columns are viewer state. The saved ViewerConfig is the public
# inspection and replay artifact.

# %%
perspective_start = time.perf_counter()
perspective_server = Server()
perspective_client = perspective_server.new_local_client()
perspective_frame = requests.assign(
    service=requests["service"].astype(str),
    region=requests["region"].astype(str),
)
perspective_table = perspective_client.table(
    perspective_frame,
    name="request_metrics",
)
perspective_view_config = {
    "columns": [
        "request_id",
        "service",
        "region",
        "payload_kb",
        "latency_ms",
        "error",
    ],
    "sort": [["latency_ms", "desc"]],
}
perspective_view = perspective_table.view(**perspective_view_config)
perspective_records = perspective_view.to_records()
perspective_schema = perspective_table.schema()
assert perspective_table.size() == ROW_COUNT
assert len(perspective_records) == ROW_COUNT

viewer_config = {
    "table": "request_metrics",
    "plugin": "Datagrid",
    **perspective_view_config,
    "settings": True,
    "theme": "Pro Light",
}
(EVIDENCE / "perspective-viewer-config.json").write_text(
    json.dumps(viewer_config, indent=2) + "\n",
    encoding="utf-8",
)

perspective_rows_json = json.dumps(
    perspective_frame.to_dict(orient="records"),
    separators=(",", ":"),
).replace("</", "<\\/")
perspective_config_json = json.dumps(
    viewer_config,
    separators=(",", ":"),
).replace("</", "<\\/")
perspective_template = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@perspective-dev/viewer@5.2.0/dist/css/themes.css">
<style>
html,body{height:100%;margin:0;background:#fffdf8;font-family:system-ui,sans-serif}
#status,#trace{padding:8px 12px;color:#5e6b70;font-size:12px}
#trace{white-space:pre-wrap;background:#f6f3ec;margin:0}
perspective-viewer{height:calc(100% - 116px);width:100%}
</style></head><body>
<div id="status">loading Table, View, viewer, and Datagrid plugin…</div>
<pre id="trace"></pre>
<perspective-viewer id="viewer"></perspective-viewer>
<script type="module">
import "https://cdn.jsdelivr.net/npm/@perspective-dev/viewer@5.2.0/dist/cdn/perspective-viewer.js";
import "https://cdn.jsdelivr.net/npm/@perspective-dev/viewer-datagrid@5.2.0/dist/cdn/perspective-viewer-datagrid.js";
import perspective from "https://cdn.jsdelivr.net/npm/@perspective-dev/client@5.2.0/dist/cdn/perspective.js";
const rows = __ROWS__;
const config = __CONFIG__;
const status = document.querySelector("#status");
const trace = document.querySelector("#trace");
try {
  const worker = await perspective.worker();
  await worker.table(rows, {name: "request_metrics"});
  const viewer = document.querySelector("#viewer");
  await viewer.load(worker);
  await viewer.restore(config);
  const saved = await viewer.save();
  status.textContent = rows.length.toLocaleString() + " prepared rows · Datagrid plugin";
  trace.textContent = JSON.stringify({
    publicCheckpoint: "viewer.save()",
    table: saved.table,
    plugin: saved.plugin,
    columns: saved.columns,
    sort: saved.sort
  }, null, 2);
  window.PERSPECTIVE_LAB = {worker, viewer, rows, saved};
} catch (error) {
  status.textContent = "Perspective failed: " + (error.message || error);
  status.style.color = "#b8423e";
  console.error(error);
}
</script></body></html>"""
perspective_html = (
    perspective_template.replace("__ROWS__", perspective_rows_json)
    .replace("__CONFIG__", perspective_config_json)
)
perspective_path = ARTIFACTS / "perspective-plugin-boundary.html"
perspective_path.write_text(perspective_html, encoding="utf-8")
perspective_build_ms = (time.perf_counter() - perspective_start) * 1_000

perspective_trace = {
    "table_rows": perspective_table.size(),
    "schema": perspective_schema,
    "view_rows": len(perspective_records),
    "view_config": perspective_view_config,
    "viewer_config": viewer_config,
    "plugin_boundary": "Datagrid",
    "html_bytes": perspective_path.stat().st_size,
}
display(
    layer_path(
        [
            ("Table", "typed prepared rows"),
            ("View", "columns + sort"),
            ("viewer", "saved presentation state"),
            ("plugin", "Datagrid renderer"),
            ("DOM", "plugin-owned output"),
        ]
    )
)
display(iframe(perspective_path, height=700))
display(
    cards(
        [
            ("Table", f"{perspective_table.size():,} rows", "typed engine state"),
            ("View", f"{len(perspective_records):,} rows", "no aggregation"),
            ("saved config", f"{len(json.dumps(viewer_config)):,} bytes", "public replay state"),
            ("plugin", "Datagrid", "renderer boundary"),
        ]
    )
)
display(pd.DataFrame(perspective_records).head(10).round(2).style.hide(axis="index"))
display(bounded_json(perspective_trace))

perspective_view.delete()
perspective_table.delete()
perspective_client.terminate()

# %% [markdown]
# ### The Perspective agent boundary
#
# Edit schema, ViewConfig, ViewerConfig, and explicit plugin options. Inspect
# 'save()', 'getView()', schema, selection events, and render statistics. Do
# not treat a plugin's internal scene as a universal Perspective scenegraph.
#
# Browser publication includes ESM, a worker, Wasm, the viewer, and plugins.
# It needs static HTTP. A live Python server is not required for this artifact
# ([save and restore](https://perspective-dev.github.io/guide/how_to/javascript/save_restore.html)).

# %% [markdown]
# ## 9. One Arrow IPC file, four projections
#
# The earlier labs embed rows in generated HTML. This section changes the data
# boundary. One local Arrow IPC file is the authority for three table
# projections and one histogram:
#
# - pandas reopens the local file with PyArrow and emits all 1,600 rows.
# - AG Grid fetches the file, decodes it with Arrow JS, and virtualizes all rows.
# - Perspective loads the Arrow bytes verbatim with no grouping or aggregation.
# - Bokeh starts with an empty source. Browser JavaScript fetches the same file,
#   computes explicit histogram bins, and updates that source.
#
# No markout file existed in the workspace, so this is a deterministic synthetic
# fixture. Positive markout values are favorable to the trade side. Replace the
# generator or file later without changing the four projection contracts.

# %%
MARKOUT_SEED = 20_260_823_09
MARKOUT_ROW_COUNT = 1_600
MARKOUT_HISTOGRAM_BINS = 48
MARKOUT_HISTOGRAM_RANGE = (-12.0, 12.0)
MARKOUT_COLUMNS = [
    "trade_id",
    "executed_at",
    "symbol",
    "side",
    "venue",
    "liquidity",
    "quantity",
    "price",
    "markout_50ms_bps",
    "markout_250ms_bps",
    "markout_1s_bps",
    "markout_5s_bps",
]

markout_rng = np.random.default_rng(MARKOUT_SEED)
markout_symbols = np.array(["AAPL", "AMZN", "META", "MSFT", "NVDA"])
markout_symbol = markout_rng.choice(
    markout_symbols,
    MARKOUT_ROW_COUNT,
    p=[0.23, 0.16, 0.15, 0.24, 0.22],
)
markout_side = markout_rng.choice(["buy", "sell"], MARKOUT_ROW_COUNT)
markout_venue = markout_rng.choice(
    ["NASDAQ", "NYSE", "ARCA", "BATS"],
    MARKOUT_ROW_COUNT,
    p=[0.36, 0.25, 0.21, 0.18],
)
markout_liquidity = markout_rng.choice(
    ["maker", "taker"],
    MARKOUT_ROW_COUNT,
    p=[0.47, 0.53],
)
markout_quantity = markout_rng.choice(
    [50, 100, 200, 300, 500, 800, 1_000],
    MARKOUT_ROW_COUNT,
    p=[0.08, 0.34, 0.23, 0.13, 0.12, 0.05, 0.05],
)
markout_base_price = pd.Series(markout_symbol).map(
    {"AAPL": 227.0, "AMZN": 202.0, "META": 548.0, "MSFT": 431.0, "NVDA": 137.0}
).to_numpy()
markout_price = markout_base_price * (
    1.0 + markout_rng.normal(0.0, 0.0018, MARKOUT_ROW_COUNT)
)
markout_offsets = np.cumsum(
    markout_rng.exponential(scale=1.45, size=MARKOUT_ROW_COUNT)
)
markout_times = pd.Timestamp("2026-08-23T13:30:00Z") + pd.to_timedelta(
    markout_offsets,
    unit="s",
)
markout_executed_at = [
    stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    for stamp in markout_times
]

symbol_tilt = pd.Series(markout_symbol).map(
    {"AAPL": 0.10, "AMZN": -0.08, "META": 0.18, "MSFT": -0.04, "NVDA": 0.22}
).to_numpy()
liquidity_tilt = np.where(markout_liquidity == "maker", -0.20, 0.12)
latent_markout = (
    markout_rng.normal(0.0, 1.35, MARKOUT_ROW_COUNT)
    + symbol_tilt
    + liquidity_tilt
)
rare_shock = np.zeros(MARKOUT_ROW_COUNT)
rare_indices = markout_rng.choice(
    MARKOUT_ROW_COUNT,
    size=32,
    replace=False,
)
rare_shock[rare_indices] = markout_rng.normal(0.0, 4.2, len(rare_indices))

def bounded_markout(scale: float, noise: float, shock_scale: float) -> np.ndarray:
    values = (
        scale * latent_markout
        + markout_rng.normal(0.0, noise, MARKOUT_ROW_COUNT)
        + shock_scale * rare_shock
    )
    return np.clip(values, -11.75, 11.75).round(4)


markouts = pd.DataFrame(
    {
        "trade_id": np.arange(1, MARKOUT_ROW_COUNT + 1, dtype=np.int32),
        "executed_at": markout_executed_at,
        "symbol": markout_symbol,
        "side": markout_side,
        "venue": markout_venue,
        "liquidity": markout_liquidity,
        "quantity": markout_quantity.astype(np.int32),
        "price": markout_price.round(4),
        "markout_50ms_bps": bounded_markout(0.32, 0.42, 0.18),
        "markout_250ms_bps": bounded_markout(0.62, 0.60, 0.38),
        "markout_1s_bps": bounded_markout(1.00, 0.82, 0.66),
        "markout_5s_bps": bounded_markout(1.35, 1.10, 1.00),
    },
    columns=MARKOUT_COLUMNS,
)

markout_schema = pa.schema(
    [
        pa.field("trade_id", pa.int32(), nullable=False),
        pa.field("executed_at", pa.string(), nullable=False),
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("side", pa.string(), nullable=False),
        pa.field("venue", pa.string(), nullable=False),
        pa.field("liquidity", pa.string(), nullable=False),
        pa.field("quantity", pa.int32(), nullable=False),
        pa.field("price", pa.float64(), nullable=False),
        pa.field("markout_50ms_bps", pa.float64(), nullable=False),
        pa.field("markout_250ms_bps", pa.float64(), nullable=False),
        pa.field("markout_1s_bps", pa.float64(), nullable=False),
        pa.field("markout_5s_bps", pa.float64(), nullable=False),
    ],
    metadata={
        b"dataset_id": b"synthetic-markout-trades-v1",
        b"markout_sign": b"positive-is-favorable-to-trade-side",
        b"seed": str(MARKOUT_SEED).encode(),
    },
)
markout_arrow_table = pa.Table.from_pandas(
    markouts,
    schema=markout_schema,
    preserve_index=False,
)
markout_path = DATA / "markouts.arrow"
with pa.OSFile(str(markout_path), "wb") as markout_sink:
    with pa_ipc.new_file(markout_sink, markout_arrow_table.schema) as markout_writer:
        markout_writer.write_table(markout_arrow_table)

with pa.memory_map(str(markout_path), "r") as markout_source:
    markout_loaded_table = pa_ipc.open_file(markout_source).read_all()
markouts_loaded = markout_loaded_table.to_pandas()
markout_sha256 = hashlib.sha256(markout_path.read_bytes()).hexdigest()
markout_histogram_counts, markout_histogram_edges = np.histogram(
    markouts_loaded["markout_1s_bps"],
    bins=MARKOUT_HISTOGRAM_BINS,
    range=MARKOUT_HISTOGRAM_RANGE,
)

assert markout_loaded_table.num_rows == MARKOUT_ROW_COUNT
assert markout_loaded_table.column_names == MARKOUT_COLUMNS
assert markouts_loaded["trade_id"].is_unique
assert markouts_loaded["trade_id"].tolist() == list(
    range(1, MARKOUT_ROW_COUNT + 1)
)
assert np.isfinite(
    markouts_loaded.filter(like="markout_").to_numpy()
).all()
assert int(markout_histogram_counts.sum()) == MARKOUT_ROW_COUNT

markout_data_receipt = {
    "dataset_id": "synthetic-markout-trades-v1",
    "relative_url": "data/markouts.arrow",
    "seed": MARKOUT_SEED,
    "rows": MARKOUT_ROW_COUNT,
    "columns": MARKOUT_COLUMNS,
    "schema": str(markout_loaded_table.schema),
    "sha256": markout_sha256,
    "bytes": markout_path.stat().st_size,
    "histogram": {
        "field": "markout_1s_bps",
        "bins": MARKOUT_HISTOGRAM_BINS,
        "range": list(MARKOUT_HISTOGRAM_RANGE),
        "count_total": int(markout_histogram_counts.sum()),
    },
    "synthetic": True,
}
(EVIDENCE / "markout-data-receipt.json").write_text(
    json.dumps(markout_data_receipt, indent=2) + "\n",
    encoding="utf-8",
)

display(
    layer_path(
        [
            ("generator", "deterministic source"),
            ("Arrow IPC", "one typed file"),
            ("local / HTTP", "two transport adapters"),
            ("four projections", "one data identity"),
        ]
    )
)
display(
    cards(
        [
            ("trades", f"{MARKOUT_ROW_COUNT:,}", "exact Arrow row count"),
            ("Arrow file", f"{markout_path.stat().st_size / 1024:.1f} KiB", "HTTP-readable IPC"),
            ("SHA-256", markout_sha256[:16] + "…", "dataset identity"),
            ("1s histogram", f"{markout_histogram_counts.sum():,}", "independent bin total"),
        ]
    )
)

pandas_markout_html = markouts_loaded.to_html(
    index=False,
    classes="markout-pandas-table",
    border=0,
    float_format=lambda value: f"{value:.4f}",
)
display(
    HTML(
        """
<style>
.markout-pandas-shell{border:1px solid #d9d3c6;border-radius:14px;background:#fffdf8;
overflow:hidden}.markout-pandas-head{display:flex;justify-content:space-between;gap:1rem;
padding:10px 12px;background:#f6f3ec;font:600 13px system-ui,sans-serif}
.markout-pandas-scroll{height:440px;overflow:auto}
.markout-pandas-table{border-collapse:collapse;width:max-content;min-width:100%;
font:12px system-ui,sans-serif}.markout-pandas-table th{position:sticky;top:0;z-index:2;
background:#172126;color:white;text-align:left}.markout-pandas-table th,
.markout-pandas-table td{padding:6px 8px;border-bottom:1px solid #e6e0d4;
white-space:nowrap}.markout-pandas-table tbody tr:nth-child(even){background:#faf8f2}
</style>
<div class="markout-pandas-shell" data-markout-view="pandas" data-rows="1600">
  <div class="markout-pandas-head">
    <span>pandas DataFrame projection · all 1,600 rows in this DOM</span>
    <span>source: data/markouts.arrow</span>
  </div>
  <div class="markout-pandas-scroll">
"""
        + pandas_markout_html
        + """
  </div>
</div>
"""
    )
)

# %% [markdown]
# ### AG Grid and Perspective: two verbatim browser tables
#
# Both tables request 'data/markouts.arrow' through one host-level promise.
# AG Grid decodes its buffer copy through Arrow JS. Perspective accepts its
# buffer copy directly. Neither table owns a second data artifact. Sorting,
# filtering, column widths, and pagination are view state.

# %%
markout_resolver_js = browser_data_resolver_js("data/markouts.arrow")
ag_grid_fragment_template = r"""
<style>
#markout-ag-grid-fragment{height:640px;border:1px solid #d9d3c6;border-radius:14px;
overflow:hidden;background:#fffdf8;color:#172126;font-family:system-ui,sans-serif}
#markout-ag-grid-fragment header{padding:12px 14px 8px}
#markout-ag-grid-fragment h3{margin:0 0 4px}
#markout-ag-grid-fragment .status{font-size:12px;color:#5e6b70;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.status[data-state=error]{color:#b8423e}
#markout-ag-grid{height:calc(100% - 68px);width:100%}
</style>
<section id="markout-ag-grid-fragment" data-markout-fragment="ag-grid">
  <header><h3>AG Grid Community · verbatim trades</h3>
  <div class="status">fetching Arrow IPC…</div></header>
  <div id="markout-ag-grid"></div>
</section>
<script>
(async () => {
const {tableFromIPC} = await import("https://cdn.jsdelivr.net/npm/apache-arrow@21.2.0/+esm");
const {AllCommunityModule, ModuleRegistry, createGrid, themeQuartz} =
  await import("https://cdn.jsdelivr.net/npm/ag-grid-community@36.1.0/+esm");
ModuleRegistry.registerModules([AllCommunityModule]);
__RESOLVER__
const root = document.querySelector("#markout-ag-grid-fragment");
const status = root.querySelector(".status");
try {
  const buffer = await loadSharedReportBuffer(dataUrl);
  const bytes = new Uint8Array(buffer.slice(0));
  const table = tableFromIPC(bytes);
  const rows = Array.from({length: table.numRows}, (_, index) =>
    table.get(index).toJSON()
  );
  const markoutFormatter = ({value}) => Number(value).toFixed(4);
  const gridOptions = {
    theme: themeQuartz.withParams({accentColor:"#2764ae", spacing:6}),
    rowData: rows,
    columnDefs: [
      {field:"trade_id", width:100, pinned:"left", filter:"agNumberColumnFilter"},
      {field:"executed_at", width:205},
      {field:"symbol", width:100, filter:true},
      {field:"side", width:90, filter:true},
      {field:"venue", width:105, filter:true},
      {field:"liquidity", width:105, filter:true},
      {field:"quantity", width:110, filter:"agNumberColumnFilter"},
      {field:"price", width:105, valueFormatter:({value}) => Number(value).toFixed(4)},
      {field:"markout_50ms_bps", headerName:"50ms bps", width:120, valueFormatter:markoutFormatter},
      {field:"markout_250ms_bps", headerName:"250ms bps", width:120, valueFormatter:markoutFormatter},
      {field:"markout_1s_bps", headerName:"1s bps", width:110, valueFormatter:markoutFormatter},
      {field:"markout_5s_bps", headerName:"5s bps", width:110, valueFormatter:markoutFormatter}
    ],
    defaultColDef: {sortable:true, resizable:true},
    pagination: true,
    paginationPageSize: 50,
    paginationPageSizeSelector: [25, 50, 100],
    getRowId: ({data}) => String(data.trade_id),
    animateRows: false
  };
  const api = createGrid(root.querySelector("#markout-ag-grid"), gridOptions);
  status.dataset.state = "ready";
  status.textContent = rows.length.toLocaleString() + " rows · "
    + (bytes.byteLength / 1024).toFixed(1) + " KiB · " + dataUrl;
  window.MARKOUT_AG_GRID = {
    api, table, rows, dataUrl, bytes:bytes.byteLength, embedding:"fragment"
  };
} catch (error) {
  status.dataset.state = "error";
  status.textContent = "AG Grid failed: " + (error.message || error);
  console.error(error);
}
})();
</script>"""
ag_grid_fragment_html = ag_grid_fragment_template.replace(
    "__RESOLVER__", markout_resolver_js
)
ag_grid_html = (
    '<!doctype html><html><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width"></head><body>'
    + ag_grid_fragment_html
    + "</body></html>"
)
ag_grid_path = ARTIFACTS / "markouts-ag-grid.html"
ag_grid_path.write_text(ag_grid_html, encoding="utf-8")

markout_perspective_columns = MARKOUT_COLUMNS
markout_perspective_config = {
    "table": "markout_trades",
    "plugin": "Datagrid",
    "columns": markout_perspective_columns,
    "group_by": [],
    "split_by": [],
    "filter": [],
    "sort": [],
    "aggregates": {},
    "settings": True,
    "theme": "Pro Light",
}
markout_perspective_fragment_template = r"""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@perspective-dev/viewer@5.2.0/dist/css/themes.css">
<style>
#markout-perspective-fragment{height:640px;border:1px solid #d9d3c6;border-radius:14px;
overflow:hidden;background:#fffdf8;color:#172126;font-family:system-ui,sans-serif}
#markout-perspective-fragment header{padding:12px 14px 8px}
#markout-perspective-fragment h3{margin:0 0 4px}
#markout-perspective-fragment .status{font-size:12px;color:#5e6b70;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.status[data-state=error]{color:#b8423e}
#markout-perspective-viewer{height:calc(100% - 68px);width:100%}
</style>
<section id="markout-perspective-fragment" data-markout-fragment="perspective">
  <header><h3>Perspective · verbatim trades</h3>
  <div class="status">fetching Arrow IPC…</div></header>
  <perspective-viewer id="markout-perspective-viewer"></perspective-viewer>
</section>
<script>
(async () => {
await import("https://cdn.jsdelivr.net/npm/@perspective-dev/viewer@5.2.0/dist/cdn/perspective-viewer.js");
await import("https://cdn.jsdelivr.net/npm/@perspective-dev/viewer-datagrid@5.2.0/dist/cdn/perspective-viewer-datagrid.js");
const perspective = (await import("https://cdn.jsdelivr.net/npm/@perspective-dev/client@5.2.0/dist/cdn/perspective.js")).default;
__RESOLVER__
const root = document.querySelector("#markout-perspective-fragment");
const status = root.querySelector(".status");
try {
  const buffer = await loadSharedReportBuffer(dataUrl);
  const bytes = new Uint8Array(buffer.slice(0));
  const worker = await perspective.worker();
  const table = await worker.table(bytes, {name:"markout_trades"});
  const viewer = root.querySelector("#markout-perspective-viewer");
  await viewer.load(worker);
  await viewer.restore(__CONFIG__);
  const saved = await viewer.save();
  const rows = await table.size();
  status.dataset.state = "ready";
  status.textContent = rows.toLocaleString() + " rows · "
    + (bytes.byteLength / 1024).toFixed(1) + " KiB · " + dataUrl;
  window.MARKOUT_PERSPECTIVE = {
    worker, table, viewer, saved, rows, dataUrl, bytes:bytes.byteLength,
    embedding:"fragment"
  };
} catch (error) {
  status.dataset.state = "error";
  status.textContent = "Perspective failed: " + (error.message || error);
  console.error(error);
}
})();
</script>"""
markout_perspective_fragment_html = (
    markout_perspective_fragment_template.replace(
        "__RESOLVER__", markout_resolver_js
    )
    .replace(
        "__CONFIG__",
        json.dumps(markout_perspective_config, separators=(",", ":")),
    )
)
markout_perspective_html = (
    '<!doctype html><html><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width"></head><body>'
    + markout_perspective_fragment_html
    + "</body></html>"
)
markout_perspective_path = ARTIFACTS / "markouts-perspective.html"
markout_perspective_path.write_text(
    markout_perspective_html,
    encoding="utf-8",
)

display(
    HTML(
        """
<style>
.markout-browser-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:1000px){.markout-browser-grid{grid-template-columns:1fr}}
</style>
<div class="markout-browser-grid">
"""
        + ag_grid_fragment_html
        + markout_perspective_fragment_html
        + "</div>"
    )
)

# %% [markdown]
# ### Bokeh histogram: empty model first, Arrow fetch second
#
# Bokeh owns the chart model, but not the trade data. The saved document starts
# with an empty 'ColumnDataSource'. A module script resolves the report URI,
# fetches Arrow, computes fixed bins, and updates the source. Use the selector
# to compare horizons. The histogram count must remain 1,600.

# %%
def build_markout_histogram() -> tuple[ColumnDataSource, object]:
    source = ColumnDataSource(
        data={"left": [], "right": [], "count": []},
        name="markout_histogram_source",
    )
    plot = figure(
        sizing_mode="stretch_width",
        height=430,
        x_range=MARKOUT_HISTOGRAM_RANGE,
        y_range=(0, 520),
        title="Markout distribution · waiting for Arrow IPC",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        name="markout_histogram_plot",
    )
    plot.quad(
        left="left",
        right="right",
        bottom=0,
        top="count",
        source=source,
        fill_color="#2764ae",
        fill_alpha=0.72,
        line_color="#fffdf8",
        line_width=0.7,
    )
    plot.add_layout(
        Span(
            location=0,
            dimension="height",
            line_color="#b8423e",
            line_dash="dashed",
            line_width=1.2,
        )
    )
    plot.xaxis.axis_label = "signed markout (basis points)"
    plot.yaxis.axis_label = "trades per 0.5 bps bin"
    return source, plot


_, markout_histogram_plot = build_markout_histogram()
markout_histogram_html = standalone_bokeh_html(
    markout_histogram_plot,
    "Arrow-backed Bokeh markout histogram",
    resources=CDN,
)
markout_histogram_html = markout_histogram_html.replace(
    "<body>",
    """<body>
<style>
body{margin:12px;background:#fffdf8;color:#172126;font-family:system-ui,sans-serif}
.markout-controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;
padding:8px 10px;background:#f6f3ec;border:1px solid #d9d3c6;border-radius:10px}
.markout-controls label{font-weight:650}.markout-controls select{padding:6px 9px}
#markout-histogram-status{font-size:12px;color:#5e6b70;min-width:0;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style>
<section id="markout-bokeh-fragment" data-markout-fragment="bokeh">
<div class="markout-controls">
  <label for="markout-horizon">Histogram horizon</label>
  <select id="markout-horizon">
    <option value="markout_50ms_bps">50 milliseconds</option>
    <option value="markout_250ms_bps">250 milliseconds</option>
    <option value="markout_1s_bps" selected>1 second</option>
    <option value="markout_5s_bps">5 seconds</option>
  </select>
  <span id="markout-histogram-status">fetching Arrow IPC…</span>
</div>""",
)
markout_histogram_runtime = r"""
<script>
(async () => {
const {tableFromIPC} = await import("https://cdn.jsdelivr.net/npm/apache-arrow@21.2.0/+esm");
__RESOLVER__
const root = document.querySelector("#markout-bokeh-fragment");
const status = root.querySelector("#markout-histogram-status");
const selector = root.querySelector("#markout-horizon");
const buffer = await loadSharedReportBuffer(dataUrl);
const bytes = new Uint8Array(buffer.slice(0));
const table = tableFromIPC(bytes);
const rows = Array.from({length:table.numRows}, (_, index) =>
  table.get(index).toJSON()
);
while (!window.Bokeh?.documents?.length) {
  await new Promise(resolve => setTimeout(resolve, 20));
}
const documentModel = Bokeh.documents.find(
  candidate => candidate.get_model_by_name("markout_histogram_source")
);
const source = documentModel.get_model_by_name("markout_histogram_source");
const plot = documentModel.get_model_by_name("markout_histogram_plot");
const lower = -12;
const upper = 12;
const binCount = 48;
const binWidth = (upper - lower) / binCount;

function update(field) {
  const counts = Array(binCount).fill(0);
  for (const row of rows) {
    const value = Number(row[field]);
    let index = Math.floor((value - lower) / binWidth);
    if (value === upper) index = binCount - 1;
    if (index >= 0 && index < binCount) counts[index] += 1;
  }
  const left = counts.map((_, index) => lower + index * binWidth);
  const right = left.map(value => value + binWidth);
  source.data = {left, right, count:counts};
  source.change.emit();
  const total = counts.reduce((sum, value) => sum + value, 0);
  plot.title.text = field + " · " + total.toLocaleString() + " trades";
  status.textContent = total.toLocaleString() + " rows binned · "
    + (bytes.byteLength / 1024).toFixed(1) + " KiB · " + dataUrl;
  window.MARKOUT_BOKEH_HISTOGRAM = {
    table, rows, source, plot, dataUrl, bytes:bytes.byteLength,
    field, counts, total, lower, upper, binCount, embedding:"fragment"
  };
}
selector.addEventListener("change", () => update(selector.value));
update(selector.value);
})();
</script>
"""
markout_histogram_html = markout_histogram_html.replace(
    "</body>",
    "</section>"
    + markout_histogram_runtime.replace("__RESOLVER__", markout_resolver_js)
    + "</body>",
)
markout_histogram_path = ARTIFACTS / "markouts-bokeh-histogram.html"
markout_histogram_path.write_text(
    markout_histogram_html,
    encoding="utf-8",
)

_, markout_histogram_fragment_plot = build_markout_histogram()
markout_bokeh_item = json_item(
    markout_histogram_fragment_plot,
    target="markout-bokeh-target",
)
markout_bokeh_fragment_runtime = (
    r"""
<script>
(async () => {
function loadReportScript(url) {
  window.__REPORT_SCRIPT_PROMISES__ ??= new Map();
  if (!window.__REPORT_SCRIPT_PROMISES__.has(url)) {
    const pending = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = url;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Script load failed: " + url));
      document.head.appendChild(script);
    });
    window.__REPORT_SCRIPT_PROMISES__.set(url, pending);
  }
  return window.__REPORT_SCRIPT_PROMISES__.get(url);
}
await loadReportScript("https://cdn.bokeh.org/bokeh/release/bokeh-3.9.2.min.js");
await Bokeh.embed.embed_item(__BOKEH_ITEM__);
"""
    + markout_histogram_runtime.replace("<script>\n(async () => {\n", "")
    .replace("})();\n</script>\n", "")
    .replace("__RESOLVER__", markout_resolver_js)
    + "})();\n</script>\n"
).replace(
    "__BOKEH_ITEM__",
    json.dumps(markout_bokeh_item, separators=(",", ":")),
)
markout_bokeh_fragment_html = (
    """
<style>
#markout-bokeh-fragment{border:1px solid #d9d3c6;border-radius:14px;
background:#fffdf8;color:#172126;font-family:system-ui,sans-serif;padding:12px}
#markout-bokeh-fragment .markout-controls{display:flex;align-items:center;gap:12px;
flex-wrap:wrap;padding:8px 10px;background:#f6f3ec;border:1px solid #d9d3c6;
border-radius:10px;margin-bottom:8px}
#markout-bokeh-fragment .markout-controls label{font-weight:650}
#markout-bokeh-fragment .markout-controls select{padding:6px 9px}
#markout-histogram-status{font-size:12px;color:#5e6b70;min-width:0;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style>
<section id="markout-bokeh-fragment" data-markout-fragment="bokeh">
  <div class="markout-controls">
    <label for="markout-horizon">Histogram horizon</label>
    <select id="markout-horizon">
      <option value="markout_50ms_bps">50 milliseconds</option>
      <option value="markout_250ms_bps">250 milliseconds</option>
      <option value="markout_1s_bps" selected>1 second</option>
      <option value="markout_5s_bps">5 seconds</option>
    </select>
    <span id="markout-histogram-status">fetching Arrow IPC…</span>
  </div>
"""
    + '<div id="markout-bokeh-target"></div>'
    + "</section>"
    + markout_bokeh_fragment_runtime
)
display(
    HTML(markout_bokeh_fragment_html)
)
display(
    cards(
        [
            ("data authority", "data/markouts.arrow", "one file for all views"),
            ("browser tables", "AG Grid + Perspective", "1,600 rows each"),
            ("pandas DOM", "1,600 rows", "bounded scroll, not truncated"),
            ("histogram bins", str(MARKOUT_HISTOGRAM_BINS), "count total = 1,600"),
        ]
    )
)

# %% [markdown]
# ### Inspect report costs through the CLI
#
# This report does not own a tailored size interface. The executable-report CLI
# inspects every report with one JSON-first contract. Run `report inspect .` for
# the machine record. Add `--render` to write the derived `report.inspect.html`
# human view. The CLI keeps serialized bytes, parsed DOM elements, and execution
# counts in separate dimensions and states their accounting boundaries.

# %%
markout_size_tree = json.loads(
    (EVIDENCE / "markout-size-tree.json").read_text(encoding="utf-8")
)

# %% [markdown]
# ### Do these projections require iframes? No.
#
# The markout projections now use `BrowserFragment` directly in the host DOM.
# AG Grid mounts into one scoped container. Perspective mounts its standard
# `<perspective-viewer>` custom element. Bokeh loads one pinned core script and
# embeds a JSON item. The existing `window.MARKOUT_*` inspection API is unchanged.
#
# One host-level promise fetches Arrow once. Each adapter gets a copied buffer,
# so Perspective cannot detach bytes that AG Grid or Bokeh still needs. Browser
# module and script caches reuse pinned dependencies. This removes duplicate
# transport without adding a widget framework or a new Python package.
#
# A native-first consolidation should use two output contracts:
#
# 1. `BrowserFragment`: scoped HTML, dependencies, and a mount function in the
#    host document. All four markout projections now use this form. Bokeh emits
#    an [embedded JSON item](https://docs.bokeh.org/en/latest/docs/reference/embed.html),
#    and Perspective can mount its standard
#    [`<perspective-viewer>` custom element](https://perspective-dev.github.io/viewer/modules/perspective-viewer.html)
#    directly.
# 2. `BrowserDocument`: an iframe fallback when global CSS, incompatible
#    dependency versions, or security isolation requires a separate document.
#
# AG Grid documents a JavaScript `createGrid(container, options)` mount API,
# not a Python/Jupyter renderer
# ([quick start](https://www.ag-grid.com/javascript-data-grid/getting-started/)).
# Its dual-host primitive would therefore be our `BrowserFragment` adapter, not
# a library-native notebook object. Perspective's Python widget is also not
# needed here; the browser custom element already fits the client-only boundary.
#
# Removing iframes does not remove Jupyter's security boundary. JupyterLab
# sanitizes saved HTML and JavaScript until the notebook is trusted
# ([JupyterLab trust model](https://jupyterlab.readthedocs.io/en/stable/user/notebook.html#trust)).
# The build therefore trusts the executed notebook before Quarto rendering and
# JupyterLab acceptance. `BrowserDocument` remains available for the six older
# isolation labs, but it is no longer the markout-section default.

# %% [markdown]
# ### JupyterLab and Quarto parity
#
# The three browser fragments are the same saved `text/html` outputs in both
# hosts. Their adapter resolves 'data/markouts.arrow' through Jupyter's '/files/'
# route for tree or '/notebooks/' URLs. In static HTML it uses the ordinary
# report-relative URL. The host owns one shared fetch and the visible tables and
# chart preserve the same public runtime objects in both cases.

# %% [markdown]
# ## 10. Mosaic coordinator as a shared analytical plane
#
# The preceding AG Grid, Perspective, and Bokeh examples remain independent on
# purpose: each demonstrates its native Arrow loading and data adapter. This
# additive lab changes the architecture, not those examples. It loads the same
# Arrow file into one DuckDB-Wasm table and registers three non-vgplot renderers
# as Mosaic clients.
#
# The report owns a plain semantic state: selected symbol, side, venue,
# liquidity, and markout horizon. Mosaic projects the filters into SQL and
# coordinates query execution. AG Grid and Perspective declare the same detail
# query, so Mosaic can consolidate them into one physical request. Bokeh declares
# a different query: DuckDB groups the filtered trades into 48 fixed bins, and
# Bokeh only renders those aggregate rows.
#
# ```text
# data/markouts.arrow -> DuckDB-Wasm -> Mosaic Coordinator
#                                           |
#                         +-----------------+-----------------+
#                         |                 |                 |
#                   AG Grid client    Perspective client   Bokeh client
#                   row objects       Arrow IPC            48 bin rows
# ```
#
# Change a filter below. Both tables and the histogram must show the same
# verified trade count. The trace panel reports the semantic state, logical
# clients, physical connector requests, and independent DuckDB count.

# %%
mosaic_coordinator_contract = {
    "schema_version": "0.1.0",
    "dataset": "data/markouts.arrow",
    "table": "markouts_mosaic",
    "source_rows": MARKOUT_ROW_COUNT,
    "state_fields": ["symbol", "side", "venue", "liquidity", "horizon"],
    "clients": {
        "ag_grid": "filtered detail rows as objects",
        "perspective": "the same filtered detail rows as Arrow IPC",
        "bokeh_histogram": "48 DuckDB-grouped bin rows",
    },
    "invariants": [
        "one Arrow insertion into one DuckDB-Wasm table",
        "one shared Mosaic Selection for all filters",
        "two identical detail queries consolidate to one physical request",
        "AG Grid rows = Perspective rows = histogram total = direct SQL count",
        "renderers do not compute filters or histogram bins",
    ],
    "browser_packages": {
        "mosaic-core": "0.30.0",
        "mosaic-sql": "0.30.0",
        "flechette": "2.5.0",
        "ag-grid-community": "36.1.0",
        "perspective": "5.2.0",
        "bokeh": "3.9.2",
    },
}
(EVIDENCE / "mosaic-coordinator-contract.json").write_text(
    json.dumps(mosaic_coordinator_contract, indent=2) + "\n",
    encoding="utf-8",
)


def build_mosaic_coordinator_histogram() -> tuple[ColumnDataSource, object]:
    source = ColumnDataSource(
        data={"left": [], "right": [], "count": []},
        name="mosaic_coordinator_histogram_source",
    )
    plot = figure(
        sizing_mode="stretch_width",
        height=390,
        x_range=MARKOUT_HISTOGRAM_RANGE,
        y_range=(0, 520),
        title="Mosaic-coordinated histogram · waiting for DuckDB",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        name="mosaic_coordinator_histogram_plot",
    )
    plot.quad(
        left="left",
        right="right",
        bottom=0,
        top="count",
        source=source,
        fill_color="#0f766e",
        fill_alpha=0.76,
        line_color="#fffdf8",
        line_width=0.7,
    )
    plot.add_layout(
        Span(
            location=0,
            dimension="height",
            line_color="#b8423e",
            line_dash="dashed",
            line_width=1.2,
        )
    )
    plot.xaxis.axis_label = "signed markout (basis points)"
    plot.yaxis.axis_label = "coordinator-filtered trades per 0.5 bps bin"
    return source, plot


_, mosaic_coordinator_histogram_plot = build_mosaic_coordinator_histogram()
mosaic_coordinator_bokeh_item = json_item(
    mosaic_coordinator_histogram_plot,
    target="mosaic-coordinator-bokeh-target",
)
mosaic_coordinator_resolver_js = browser_data_resolver_js("data/markouts.arrow")
mosaic_coordinator_fragment_template = r"""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@perspective-dev/viewer@5.2.0/dist/css/themes.css">
<style>
#markout-mosaic-coordinator{border:1px solid #cfc8ba;border-radius:16px;
background:#fffdf8;color:#172126;font-family:system-ui,sans-serif;overflow:hidden}
#markout-mosaic-coordinator .mc-head{padding:14px 16px;background:#eef6f3;
border-bottom:1px solid #cfc8ba}.mc-head h3{margin:0 0 5px}.mc-status{font-size:12px;
color:#53656a}.mc-status[data-state=error]{color:#b8423e}
#markout-mosaic-coordinator .mc-controls{display:flex;gap:10px;align-items:end;
flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid #ded8cc}
#markout-mosaic-coordinator label{display:grid;gap:4px;font-size:12px;font-weight:650}
#markout-mosaic-coordinator select,#markout-mosaic-coordinator button{padding:6px 9px;
border:1px solid #aaa397;border-radius:7px;background:white;color:#172126}
#markout-mosaic-coordinator button{cursor:pointer;font-weight:650}
#markout-mosaic-coordinator .mc-kpis{display:grid;
grid-template-columns:repeat(5,minmax(110px,1fr));gap:8px;padding:12px 16px}
#markout-mosaic-coordinator .mc-kpi{padding:9px 10px;border:1px solid #d9d3c6;
border-radius:10px;background:#fff}.mc-kpi strong{display:block;font-size:18px;color:#0f766e}
#markout-mosaic-coordinator .mc-kpi span{font-size:11px;color:#5e6b70}
#markout-mosaic-coordinator .mc-grid{display:grid;grid-template-columns:1fr 1fr;
gap:12px;padding:0 16px 14px}.mc-panel{border:1px solid #d9d3c6;border-radius:12px;
overflow:hidden;background:white}.mc-panel h4{margin:0;padding:9px 11px;background:#f6f3ec;
font-size:13px}.mc-widget-status{padding:0 11px 8px;background:#f6f3ec;color:#5e6b70;
font-size:11px}.mc-widget-status[data-state=error]{color:#b8423e}
#mosaic-coordinator-ag-grid,#mosaic-coordinator-perspective{height:470px;width:100%}
#markout-mosaic-coordinator .mc-histogram{margin:0 16px 14px;padding:10px}
#markout-mosaic-coordinator .mc-trace{margin:0 16px 16px;padding:10px 12px;
max-height:260px;overflow:auto;background:#172126;color:#d9f5ed;border-radius:10px;
font:11px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap}
@media(max-width:1000px){#markout-mosaic-coordinator .mc-grid{grid-template-columns:1fr}
#markout-mosaic-coordinator .mc-kpis{grid-template-columns:repeat(2,1fr)}}
</style>
<section id="markout-mosaic-coordinator" data-markout-fragment="mosaic-coordinator">
  <header class="mc-head"><h3>Mosaic coordinator · AG Grid + Perspective + Bokeh</h3>
    <div class="mc-status">initializing one DuckDB-Wasm analytical plane…</div>
  </header>
  <div class="mc-controls">
    <label>Symbol<select data-filter="symbol"><option value="">all</option>
      <option>AAPL</option><option>AMZN</option><option>META</option><option>MSFT</option><option>NVDA</option>
    </select></label>
    <label>Side<select data-filter="side"><option value="">all</option>
      <option value="buy">buy</option><option value="sell">sell</option>
    </select></label>
    <label>Venue<select data-filter="venue"><option value="">all</option>
      <option>ARCA</option><option>BATS</option><option>NASDAQ</option><option>NYSE</option>
    </select></label>
    <label>Liquidity<select data-filter="liquidity"><option value="">all</option>
      <option value="maker">maker</option><option value="taker">taker</option>
    </select></label>
    <label>Histogram horizon<select data-horizon>
      <option value="markout_50ms_bps">50 milliseconds</option>
      <option value="markout_250ms_bps">250 milliseconds</option>
      <option value="markout_1s_bps" selected>1 second</option>
      <option value="markout_5s_bps">5 seconds</option>
    </select></label>
    <button type="button" data-clear>Clear filters</button>
  </div>
  <div class="mc-kpis">
    <div class="mc-kpi"><strong data-kpi="verified">—</strong><span>direct SQL rows</span></div>
    <div class="mc-kpi"><strong data-kpi="ag-grid">—</strong><span>AG Grid rows</span></div>
    <div class="mc-kpi"><strong data-kpi="perspective">—</strong><span>Perspective rows</span></div>
    <div class="mc-kpi"><strong data-kpi="histogram">—</strong><span>histogram total</span></div>
    <div class="mc-kpi"><strong data-kpi="queries">—</strong><span>physical queries</span></div>
  </div>
  <div class="mc-grid">
    <div class="mc-panel"><h4>AG Grid · Mosaic detail client</h4>
      <div class="mc-widget-status" data-widget-status="ag-grid">waiting for query…</div>
      <div id="mosaic-coordinator-ag-grid"></div></div>
    <div class="mc-panel"><h4>Perspective · Mosaic Arrow client</h4>
      <div class="mc-widget-status" data-widget-status="perspective">waiting for query…</div>
      <perspective-viewer id="mosaic-coordinator-perspective"></perspective-viewer></div>
  </div>
  <div class="mc-panel mc-histogram"><h4>Bokeh · Mosaic SQL histogram client</h4>
    <div class="mc-widget-status" data-widget-status="histogram">waiting for query…</div>
    <div id="mosaic-coordinator-bokeh-target"></div></div>
  <pre class="mc-trace" aria-label="Mosaic coordinator trace">initializing trace…</pre>
</section>
<script>
(async () => {
const root = document.querySelector("#markout-mosaic-coordinator");
const mainStatus = root.querySelector(".mc-status");
const traceNode = root.querySelector(".mc-trace");
const widgetStatus = name => root.querySelector(`[data-widget-status="${name}"]`);
const setKpi = (name, value) => {
  root.querySelector(`[data-kpi="${name}"]`).textContent =
    Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value);
};
try {
  const [core, sql, flechette, ag, perspectiveModule] = await Promise.all([
    import("https://cdn.jsdelivr.net/npm/@uwdata/mosaic-core@0.30.0/+esm"),
    import("https://cdn.jsdelivr.net/npm/@uwdata/mosaic-sql@0.30.0/+esm"),
    import("https://cdn.jsdelivr.net/npm/@uwdata/flechette@2.5.0/+esm"),
    import("https://cdn.jsdelivr.net/npm/ag-grid-community@36.1.0/+esm"),
    import("https://cdn.jsdelivr.net/npm/@perspective-dev/client@5.2.0/dist/cdn/perspective.js"),
    import("https://cdn.jsdelivr.net/npm/@perspective-dev/viewer@5.2.0/dist/cdn/perspective-viewer.js"),
    import("https://cdn.jsdelivr.net/npm/@perspective-dev/viewer-datagrid@5.2.0/dist/cdn/perspective-viewer-datagrid.js"),
  ]).then(values => [values[0], values[1], values[2], values[3], values[4]]);
  const {Coordinator, Selection, clausePoint, makeClient, wasmConnector} = core;
  const {column} = sql;
  const {tableFromIPC, tableToIPC} = flechette;
  const perspective = perspectiveModule.default;
  ag.ModuleRegistry.registerModules([ag.AllCommunityModule]);

  function loadReportScript(url) {
    window.__REPORT_SCRIPT_PROMISES__ ??= new Map();
    if (!window.__REPORT_SCRIPT_PROMISES__.has(url)) {
      const pending = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = url;
        script.onload = resolve;
        script.onerror = () => reject(new Error("Script load failed: " + url));
        document.head.appendChild(script);
      });
      window.__REPORT_SCRIPT_PROMISES__.set(url, pending);
    }
    return window.__REPORT_SCRIPT_PROMISES__.get(url);
  }
  await loadReportScript("https://cdn.bokeh.org/bokeh/release/bokeh-3.9.2.min.js");
  await Bokeh.embed.embed_item(__BOKEH_ITEM__);
  const bokehDocument = Bokeh.documents.find(candidate =>
    candidate.get_model_by_name("mosaic_coordinator_histogram_source")
  );
  const bokehSource = bokehDocument.get_model_by_name("mosaic_coordinator_histogram_source");
  const bokehPlot = bokehDocument.get_model_by_name("mosaic_coordinator_histogram_plot");

  __RESOLVER__
  const buffer = await loadSharedReportBuffer(dataUrl);
  const arrowBytes = new Uint8Array(buffer.slice(0));
  const sourceArrowTable = tableFromIPC(arrowBytes);
  const arrowStream = tableToIPC(sourceArrowTable, {format:"stream"});
  const baseConnector = wasmConnector();
  const connection = await baseConnector.getConnection();
  await connection.insertArrowFromIPCStream(arrowStream, {name:"markouts_mosaic"});

  const physicalQueries = [];
  const tracedConnector = {
    async query(request) {
      const started = performance.now();
      const result = await baseConnector.query(request);
      physicalQueries.push({
        type: request.type || "arrow",
        sql: request.sql,
        duration_ms: Number((performance.now() - started).toFixed(2)),
      });
      return result;
    },
  };
  const coordinator = new Coordinator(tracedConnector, {
    cache:true, consolidate:true, logger:console,
  });
  const selection = Selection.intersect();
  const analyticState = {
    filters:{symbol:null, side:null, venue:null, liquidity:null},
    horizon:"markout_1s_bps",
    revision:0,
  };
  const filterSources = Object.fromEntries(
    Object.keys(analyticState.filters).map(name => [name, {name}])
  );
  const counts = {ag_grid:0, perspective:0, histogram:0, verified:0};
  const DETAIL_COLUMNS = [
    "trade_id", "executed_at", "symbol", "side", "venue", "liquidity",
    "quantity", "price", "markout_50ms_bps", "markout_250ms_bps",
    "markout_1s_bps", "markout_5s_bps",
  ];
  const HORIZONS = new Set([
    "markout_50ms_bps", "markout_250ms_bps", "markout_1s_bps", "markout_5s_bps",
  ]);

  function predicateSQL(filter) {
    const predicates = (Array.isArray(filter) ? filter : [filter])
      .filter(Boolean).map(value => `(${String(value)})`);
    return predicates.length ? `WHERE ${predicates.join(" AND ")}` : "";
  }
  const detailQuery = filter =>
    `SELECT ${DETAIL_COLUMNS.map(name => `"${name}"`).join(", ")} `
    + `FROM markouts_mosaic ${predicateSQL(filter)} ORDER BY trade_id`;
  const histogramQuery = filter => {
    const field = HORIZONS.has(analyticState.horizon)
      ? analyticState.horizon : "markout_1s_bps";
    const where = predicateSQL(filter);
    const filtered = where ? `${where} AND` : "WHERE";
    return `WITH bins AS (SELECT range AS bin FROM range(48)), counts AS (`
      + `SELECT greatest(0, least(47, floor(("${field}" + 12.0) / 0.5)::INTEGER)) AS bin, `
      + `count(*)::INTEGER AS count FROM markouts_mosaic ${filtered} `
      + `"${field}" >= -12.0 AND "${field}" <= 12.0 GROUP BY bin) `
      + `SELECT -12.0 + bins.bin * 0.5 AS left, -11.5 + bins.bin * 0.5 AS right, `
      + `coalesce(counts.count, 0)::INTEGER AS count FROM bins LEFT JOIN counts USING (bin) `
      + `ORDER BY bins.bin`;
  };

  const gridApi = ag.createGrid(root.querySelector("#mosaic-coordinator-ag-grid"), {
    theme: ag.themeQuartz.withParams({accentColor:"#0f766e", spacing:6}),
    rowData: [],
    columnDefs: [
      {field:"trade_id", width:95, pinned:"left"}, {field:"executed_at", width:190},
      {field:"symbol", width:90}, {field:"side", width:80}, {field:"venue", width:100},
      {field:"liquidity", width:100}, {field:"quantity", width:100},
      {field:"price", width:95, valueFormatter:({value}) => Number(value).toFixed(4)},
      {field:"markout_1s_bps", headerName:"1s bps", width:105,
       valueFormatter:({value}) => Number(value).toFixed(4)},
    ],
    defaultColDef:{sortable:true,resizable:true}, pagination:true,
    paginationPageSize:25, paginationPageSizeSelector:[25,50,100],
    getRowId:({data}) => String(data.trade_id), animateRows:false,
  });

  const perspectiveWorker = await perspective.worker();
  const perspectiveTable = await perspectiveWorker.table({
    trade_id:"integer", executed_at:"string", symbol:"string", side:"string",
    venue:"string", liquidity:"string", quantity:"integer", price:"float",
    markout_50ms_bps:"float", markout_250ms_bps:"float",
    markout_1s_bps:"float", markout_5s_bps:"float",
  }, {name:"mosaic_markout_result"});
  const perspectiveViewer = root.querySelector("#mosaic-coordinator-perspective");
  await perspectiveViewer.load(perspectiveWorker);
  await perspectiveViewer.restore({
    table:"mosaic_markout_result", plugin:"Datagrid", columns:DETAIL_COLUMNS,
    group_by:[], split_by:[], filter:[], sort:[], aggregates:{},
    settings:false, theme:"Pro Light",
  });
  let perspectiveUpdate = Promise.resolve();

  const agClient = makeClient({
    coordinator, selection, filterStable:false, query:detailQuery,
    queryResult(data) {
      const rows = data.toArray();
      counts.ag_grid = rows.length;
      gridApi.setGridOption("rowData", rows);
      widgetStatus("ag-grid").dataset.state = "ready";
      widgetStatus("ag-grid").textContent = `${rows.length.toLocaleString()} coordinator rows`;
      setKpi("ag-grid", rows.length);
    },
  });
  const perspectiveClient = makeClient({
    coordinator, selection, filterStable:false, query:detailQuery,
    queryResult(data) {
      const rows = data.numRows;
      counts.perspective = rows;
      perspectiveUpdate = perspectiveUpdate.then(async () => {
        await perspectiveTable.replace(tableToIPC(data));
        widgetStatus("perspective").dataset.state = "ready";
        widgetStatus("perspective").textContent = `${rows.toLocaleString()} coordinator Arrow rows`;
        setKpi("perspective", rows);
      });
    },
  });
  const histogramClient = makeClient({
    coordinator, selection, filterStable:false, query:histogramQuery,
    queryResult(data) {
      const rows = data.toArray().map(row => ({
        left:Number(row.left), right:Number(row.right), count:Number(row.count),
      }));
      const total = rows.reduce((sum, row) => sum + row.count, 0);
      counts.histogram = total;
      bokehSource.data = {
        left:rows.map(row => row.left), right:rows.map(row => row.right),
        count:rows.map(row => row.count),
      };
      bokehSource.change.emit();
      bokehPlot.title.text = `${analyticState.horizon} · ${total.toLocaleString()} coordinator rows`;
      widgetStatus("histogram").dataset.state = "ready";
      widgetStatus("histogram").textContent = `${rows.length} DuckDB bins · ${total.toLocaleString()} trades`;
      setKpi("histogram", total);
    },
  });
  const clients = [agClient, perspectiveClient, histogramClient];

  async function verify(revision = analyticState.revision) {
    await new Promise(resolve => setTimeout(resolve, 30));
    await Promise.all(clients.map(client => client.pending));
    await perspectiveUpdate;
    const where = predicateSQL(selection.predicate(null, true));
    const result = await baseConnector.query({
      type:"json", sql:`SELECT count(*)::INTEGER AS rows FROM markouts_mosaic ${where}`,
    });
    if (revision !== analyticState.revision) return verify(analyticState.revision);
    counts.verified = Number(result[0].rows);
    const equal = counts.ag_grid === counts.verified
      && counts.perspective === counts.verified
      && counts.histogram === counts.verified;
    const detailRequests = physicalQueries.filter(entry =>
      entry.sql.startsWith("SELECT \"trade_id\"")
    );
    const receipt = {
      schema_version:"0.1.0", state:JSON.parse(JSON.stringify(analyticState)),
      source:{url:dataUrl, bytes:arrowBytes.byteLength, rows:sourceArrowTable.numRows,
        ipc_file_to_stream_conversions:1, insertions:1},
      coordinator:{logical_clients:coordinator.clients.size,
        filter_groups:coordinator.filterGroups.size,
        physical_queries:physicalQueries.length,
        detail_physical_queries:detailRequests.length},
      rows:{...counts, equal},
      latest_queries:physicalQueries.slice(-6),
    };
    window.MARKOUT_MOSAIC_COORDINATOR.receipt = receipt;
    root.dataset.state = equal ? "ready" : "error";
    root.dataset.rows = String(counts.verified);
    mainStatus.dataset.state = equal ? "ready" : "error";
    mainStatus.textContent = equal
      ? `${counts.verified.toLocaleString()} verified rows · 3 clients · ${physicalQueries.length} physical queries`
      : "client totals do not match direct DuckDB verification";
    setKpi("verified", counts.verified);
    setKpi("queries", physicalQueries.length);
    traceNode.textContent = JSON.stringify(receipt, null, 2);
    return receipt;
  }

  async function setFilter(name, value) {
    if (!(name in analyticState.filters)) throw new Error(`Unknown filter: ${name}`);
    analyticState.filters[name] = value || null;
    analyticState.revision += 1;
    selection.update(clausePoint(column(name), value || undefined, {
      source:filterSources[name],
    }));
    return verify(analyticState.revision);
  }
  async function setHorizon(value) {
    if (!HORIZONS.has(value)) throw new Error(`Unknown horizon: ${value}`);
    analyticState.horizon = value;
    analyticState.revision += 1;
    await histogramClient.requestQuery();
    return verify(analyticState.revision);
  }
  for (const control of root.querySelectorAll("[data-filter]")) {
    control.addEventListener("change", () => setFilter(control.dataset.filter, control.value));
  }
  root.querySelector("[data-horizon]").addEventListener(
    "change", event => setHorizon(event.target.value)
  );
  root.querySelector("[data-clear]").addEventListener("click", async () => {
    for (const control of root.querySelectorAll("[data-filter]")) control.value = "";
    for (const name of Object.keys(analyticState.filters)) analyticState.filters[name] = null;
    analyticState.revision += 1;
    selection.reset();
    await verify(analyticState.revision);
  });

  window.MARKOUT_MOSAIC_COORDINATOR = {
    coordinator, selection, clients, gridApi, perspectiveWorker, perspectiveTable,
    perspectiveViewer, bokehSource, bokehPlot, analyticState, physicalQueries,
    setFilter, setHorizon, verify, receipt:null,
  };
  const initialReceipt = await verify();
  window.MARKOUT_MOSAIC_COORDINATOR.initialReceipt = structuredClone(initialReceipt);
} catch (error) {
  root.dataset.state = "error";
  mainStatus.dataset.state = "error";
  mainStatus.textContent = "Mosaic coordinator failed: " + (error.message || error);
  traceNode.textContent = error.stack || String(error);
  console.error("Mosaic coordinator lab failed", error);
}
})();
</script>
"""
mosaic_coordinator_fragment_html = (
    mosaic_coordinator_fragment_template.replace(
        "__BOKEH_ITEM__",
        json.dumps(mosaic_coordinator_bokeh_item, separators=(",", ":")),
    ).replace("__RESOLVER__", mosaic_coordinator_resolver_js)
)
display(HTML(mosaic_coordinator_fragment_html))

# %%
display(
    cards(
        [
            ("data authority", "markouts.arrow", "same 1,600-row artifact"),
            ("query authority", "Mosaic 0.30", "one coordinator and selection"),
            ("detail clients", "2 → 1 query", "AG Grid + Perspective consolidation"),
            ("chart client", "48 SQL bins", "Bokeh renders aggregate rows only"),
        ]
    )
)

# %% [markdown]
# ## 11. Crosswalk: edit, inspect, and avoid
#
# This table replaces the former score heatmap. It gives an agent a public edit
# target and a public verification point. It also names derived or private state
# that must not become authoritative.

# %%
architecture_records = [
    {
        "system": "Matplotlib OO",
        "lowering path": "Figure/Axes calls → Artist hierarchy → backend renderer → output",
        "edit": "Figure, Axes, and explicit Artists",
        "inspect": "findobj(), transforms, renderer, saved SVG or bitmap",
        "avoid": "pyplot global state and backend-private objects",
    },
    {
        "system": "Altair / Vega-Lite",
        "lowering path": "Python constructors → semantic JSON → Vega compilation",
        "edit": "Altair source or Vega-Lite spec",
        "inspect": "validated Vega-Lite and compiled Vega",
        "avoid": "compiled Vega as accidental source of truth",
    },
    {
        "system": "Vega",
        "lowering path": "spec → operators/signals → scenegraph → SVG or Canvas",
        "edit": "Vega spec and named signals or data",
        "inspect": "View signals, data, scales, state, and scenegraph",
        "avoid": "private runtime operators and direct scene-item mutation",
    },
    {
        "system": "Observable Runtime",
        "lowering path": "cell source → module dependency graph → returned values",
        "edit": "cell or module source",
        "inspect": "cell values, observers, and dependency results",
        "avoid": "implicit shared mutable objects across cells",
    },
    {
        "system": "D3",
        "lowering path": "JavaScript → scales/layouts → explicit DOM or Canvas mutation",
        "edit": "data joins, scales, and mutation code",
        "inspect": "DOM nodes, bound data, and scale outputs",
        "avoid": "treating final DOM as a portable semantic spec",
    },
    {
        "system": "Observable Plot",
        "lowering path": "Plot options + Marks → scales/transforms → returned DOM",
        "edit": "Plot options and Mark objects",
        "inspect": "returned DOM, scale options, and host cell value",
        "avoid": "assuming a Vega compiler or scenegraph exists",
    },
    {
        "system": "Bokeh",
        "lowering path": "Python Models → Document graph → BokehJS Views → Canvas",
        "edit": "Models, sources, ranges, and callbacks",
        "inspect": "Document JSON, model IDs, selections, and ranges",
        "avoid": "confusing standalone JS with server callbacks",
    },
    {
        "system": "Plotly",
        "lowering path": "graph_objects → Figure protocol → Plotly.js → SVG/WebGL",
        "edit": "data, layout, and frames",
        "inspect": "Figure JSON and browser event payloads",
        "avoid": "private Plotly.js rendering internals",
    },
    {
        "system": "HoloViews",
        "lowering path": "Elements/compositions → backend registry → backend model",
        "edit": "semantic Elements, operations, and options",
        "inspect": "object tree and resolved backend model",
        "avoid": "changing the backend model while claiming semantic source",
    },
    {
        "system": "Datashader",
        "lowering path": "Canvas + glyph + reduction → aggregate array → image",
        "edit": "canvas, glyph, reduction, and transfer function",
        "inspect": "aggregate array and shaded image",
        "avoid": "per-row graphical identity",
    },
    {
        "system": "Perspective",
        "lowering path": "Table → View → viewer state → plugin → DOM",
        "edit": "schema, ViewConfig, ViewerConfig, and plugin config",
        "inspect": "schema, save(), getView(), and viewer events",
        "avoid": "plugin internals as a universal scenegraph",
    },
    {
        "system": "AG Grid",
        "lowering path": "Arrow rows → row model → virtualized grid DOM",
        "edit": "column definitions, row identity, and grid options",
        "inspect": "Grid API, filter model, sort model, and rendered rows",
        "avoid": "grid view state as the source dataset",
    },
    {
        "system": "Mosaic coordinator",
        "lowering path": "semantic state → Selection/Params → coordinated SQL → renderer clients",
        "edit": "system-owned state schema and client query/result adapters",
        "inspect": "selection clauses, generated SQL, client results, and query trace",
        "avoid": "Mosaic objects or vgplot marks as the durable application state",
    },
]
architecture_df = pd.DataFrame(architecture_records)
display(HTML(architecture_df.to_html(index=False, classes="compact-table", border=0)))

# %% [markdown]
# ### One linked interaction should use semantic state
#
# “Selected service = search” is a stable host-level fact. A Bokeh row index,
# Vega signal tuple, Plotly click payload, or Perspective filter array is one
# runtime's encoding of that fact.
#
# For a mixed report, own a small application contract such as:
#
#     {selection: {service: "search"}, origin: "vega", revision: 12}
#
# Adapters can translate this contract into each runtime. The contract prevents
# a renderer from becoming the system-wide state owner.

# %% [markdown]
# ## 12. Evidence receipt and conclusions
#
# The Python execution records the public lowering checkpoints. Browser
# acceptance must still verify runtime modules, interaction, workers, Wasm, and
# console output. Construction times and file sizes are diagnostics only.

# %%
source_notes = json.loads(
    (EVIDENCE / "architecture-source-notes.json").read_text(encoding="utf-8")
)
runtime_traces = {
    "matplotlib": {
        "build_ms": matplotlib_build_ms,
        "artifact": mpl_trace,
    },
    "altair_vega": {
        "build_ms": altair_build_ms,
        "vega_lite_bytes": len(vl_json),
        "vega_bytes": len(vega_json),
        "html_bytes": altair_path.stat().st_size,
        "trace": vega_trace,
    },
    "observable_d3_plot": {
        "browser_only": True,
        "input_rows": ROW_COUNT,
        "html_bytes": observable_path.stat().st_size,
        "versions": browser_versions,
    },
    "bokeh": {
        "build_ms": bokeh_build_ms,
        "html_bytes": bokeh_path.stat().st_size,
        "trace": bokeh_trace,
    },
    "plotly": {
        "build_ms": plotly_build_ms,
        "html_bytes": plotly_path.stat().st_size,
        "trace": plotly_outline,
    },
    "holoviews": {
        "build_ms": holoviz_build_ms,
        "html_bytes": holoviz_path.stat().st_size,
        "trace": holoviz_trace,
    },
    "datashader": {
        "build_ms": datashader_build_ms,
        "trace": datashader_trace,
    },
    "perspective": {
        "build_ms": perspective_build_ms,
        "html_bytes": perspective_path.stat().st_size,
        "trace": perspective_trace,
    },
    "markout_arrow": {
        "receipt": markout_data_receipt,
        "size_tree": markout_size_tree,
        "pandas_rows": len(markouts_loaded),
        "ag_grid_html_bytes": ag_grid_path.stat().st_size,
        "perspective_html_bytes": markout_perspective_path.stat().st_size,
        "bokeh_histogram_html_bytes": markout_histogram_path.stat().st_size,
        "browser_artifacts": [
            ag_grid_path.as_posix(),
            markout_perspective_path.as_posix(),
            markout_histogram_path.as_posix(),
        ],
    },
    "mosaic_coordinator": {
        "browser_only": True,
        "contract": mosaic_coordinator_contract,
        "public_api": "window.MARKOUT_MOSAIC_COORDINATOR",
    },
}
comparison_record = {
    "record_version": "4.0.0-mosaic-coordinator",
    "dataset": {
        "seed": SEED,
        "rows": ROW_COUNT,
        "sha256": data_sha256,
        "p95_latency_ms": p95_latency,
        "errors": int(requests["error"].sum()),
    },
    "neutral_layers": [
        "authoring API",
        "semantic IR",
        "reactive or dataflow graph",
        "graphical scene",
        "renderer",
        "output surface",
        "host graph",
    ],
    "versions": package_versions,
    "browser_versions": browser_versions,
    "architecture": architecture_records,
    "runtime_traces": runtime_traces,
    "source_note_count": len(source_notes),
    "limits": [
        "One synthetic prepared dataset cannot represent all charting work.",
        "Construction timings are not cross-library performance results.",
        "Browser module versions are pinned in generated HTML, not Python metadata.",
        "Plotly, Observable, and Perspective artifacts use CDN resources.",
        "AG Grid and the browser histogram use pinned Arrow JS CDN modules.",
        "The Mosaic coordinator lab uses pinned CDN ESM modules and DuckDB-Wasm.",
        "Perspective needs static HTTP for modules, worker, and Wasm.",
        "The markout fixture is synthetic and is not trading-performance evidence.",
        "JupyterLab must trust notebook HTML outputs before fragment scripts run.",
        "Dynamic HoloViews, Datashader, or Panel pipelines can need live Python.",
        "The report inspects public checkpoints, not every private renderer stage.",
    ],
}
(EVIDENCE / "comparison-records.json").write_text(
    json.dumps(comparison_record, indent=2, default=str) + "\n",
    encoding="utf-8",
)

display(
    cards(
        [
            ("prepared rows", f"{ROW_COUNT:,}", "checksum verified"),
            ("architecture paths", str(len(architecture_records)), "no composite score"),
            ("source notes", str(len(source_notes)), "primary-source research"),
            ("machine record", "comparison-records.json", "trace backend"),
        ]
    )
)
display(
    bounded_json(
        {
            "versions": package_versions,
            "browser_versions": browser_versions,
            "limits": comparison_record["limits"],
        }
    )
)

# %% [markdown]
# ### What the architecture model changes
#
# First, “declarative” is not one layer. Vega-Lite is a semantic language;
# Vega is a lower runtime specification; a Vega View owns reactive state and a
# scenegraph. These are separate inspection points.
#
# Second, “mark” is not one object. A Vega mark definition generates mark
# items. A Plot Mark returns DOM. A Matplotlib PathCollection is a retained
# Artist that can represent many rows.
#
# Third, host reactivity is not chart reactivity. An Observable cell can own a
# Vega View, Plot chart, or D3 DOM tree. Its dependency graph surrounds those
# runtimes. A mixed Jupyter report has the same need: own semantic interaction
# state outside any one renderer.
#
# The same rule applies to data. Arrow IPC can remain the source artifact while
# pandas, AG Grid, Perspective, and Bokeh expose different projections. A table
# filter or selected histogram horizon is view state, not a new dataset.
#
# Finally, the best agent workflow follows the lowering path. Edit the highest
# stable source that still expresses the intent. Inspect each public checkpoint.
# Verify the semantic state and final output. Descend to a lower layer only when
# that descent becomes an explicit source-allocation decision.
