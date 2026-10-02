---
name: report-presentation
description: Configure report reading navigation and display output across JupyterLab and HTTP-served Quarto HTML. Use for Mermaid, MIME representations, and host display adapters.
---

# Report presentation

Own presentation choices, display integration, and their limits.
Stage: consolidation. Supported hosts are JupyterLab/notebooks and HTTP-served
HTML bundles. The [report contract](../../../docs/report-contract.md) owns
observable outcomes.

Use [table-presentation](../table-presentation/SKILL.md) for table layout,
value formatting, visual emphasis, and Great Tables / pandas Styler choices.
Use [report-delivery](../report-delivery/SKILL.md) when producing or checking saved
outputs. Analytical values and graph semantics stay with their source owners.

## Reading navigation

`components/reporting/src/executable_reports/presentation_assets/reading-format.yml` owns the default
Quarto reading profile: an expanded contents list, folded code, and Mermaid's
browser renderer with an explicit neutral theme. This avoids Quarto's
additional theme CSS overriding diagram colors. A raw Jupytext frontmatter cell carries these format settings
into the executed notebook. `_quarto.yml` owns project policy, including disabled
execution when rendering saved results.

`reading-navigation.html` is an include fragment, not a page or iframe. It
contains the progress-bar element, its CSS, and the JavaScript that updates it
and the contents highlight together. Quarto inserts the fragment through
`include-after-body`. This keeps one implementation for the two scroll controls.
The script measures the current page, so opening code panels or rendering a
diagram does not leave the progress calculation stale. It does not read data
or change analytical state. Notebook navigation remains JupyterLab's concern.

The same fragment gives each rendered Mermaid diagram an "Expand" button. The
diagram then fills the browser window and scales to it; the screen and the
browser's own controls do not change. The page stops scrolling underneath.
Escape or "Close" returns to the same reading position. Mark any other figure
with `data-report-expand` to give it the same button. The button appears only
after Mermaid has rendered, because Mermaid reads the block's text.
`report verify` checks every diagram's toggle; a report with an older fragment
gets a warning to copy the current one.

`report new` copies the reading profile into `report.py` and writes an editable
navigation fragment. Those files then belong to that report's versioned source
bundle. Updating the package does not silently change an existing report.
Examples in this repository can reference the shared source asset directly,
as semantic-tables does. The runtime behavior lives in code; the contract states
what readers must be able to do.

## Mermaid through native display hooks

Use Mermaid for pipeline and API diagrams. It has native JupyterLab support,
Quarto integration, and source that readers can use on GitHub.

```python
from IPython.display import display
from executable_reports.presentation import Mermaid

display(Mermaid(pipeline.to_graph()))
```

`Mermaid` implements IPython's `_repr_mimebundle_` hook with `text/vnd.mermaid`
and a plain-source fallback. JupyterLab uses its built-in Mermaid renderer.
The adapter does not execute data, infer edges, or own graph semantics.
Pipeline edges must derive from actual recorded computation calls.

Quarto does not directly consume that native MIME type. `report render` makes
a temporary notebook projection with Mermaid Markdown cells in the same output
order, then renders the projection. Original code appears once and other saved
outputs retain their order. The executed notebook remains unchanged and its
hash is checked. The HTML bundle includes Quarto's Mermaid runtime, which runs
in the browser over HTTP. No iframe, extra notebook extension, raster fallback,
or frontend notebook save is needed.

The pure `quarto_notebook()` adapter is also available to tools that call
Quarto directly. The compatibility probe's `render.py` shows this path.
Do not add Quarto Markdown to the notebook's MIME bundle: JupyterLab prefers
that representation, but its Mermaid fence syntax differs on this path.

Use separate diagrams for separate scopes. Keep labels readable at the content
width and add `accTitle:` and `accDescr:` for accessibility. The example uses
Mermaid's `htmlLabels: false` setting for SVG text. Graph styling belongs to the
report; the shared display adapter only carries the source between hosts.

## Other display output and verification

Use standard IPython representations. SVG suits static graphics, while HTML
supports browser controls. A MIME bundle can offer alternatives, but each must
preserve the same analysis meaning. Hosts can select different MIME types.
JavaScript controls can work in an HTTP-served static report. Python callbacks
need a running kernel or application server. Use an iframe only when isolation
is a real requirement.

In a live JupyterLab session, use **Trust Notebook** before displaying saved
browser-executable output. Trust allows JupyterLab to select and run rich MIME
renderers that can execute browser code. It does not establish analytical
correctness, and the presence of an HTML or JavaScript MIME bundle does not
prove visible rendering.
Check the actual output area when verifying Bokeh, Vega, widgets, or custom
renderers. The live session model and selected-cell execution belong to the
[notebook collaboration guide](../../../docs/notebook-collaboration.md).

The baseline report workflow defines no widget dependency or widget parity
promise. A report that uses widgets must declare and verify both host paths.
Direct Bokeh output needs the matching `jupyter_bokeh` host renderer; normal
Bokeh JavaScript callbacks remain host-specific behavior.

Raw Vega and Vega-Lite MIME output is a JupyterLab representation. Quarto does
not consume that MIME type as a static HTML fallback. When a report targets
both hosts, provide an equivalent `text/html` representation and pin its
runtime assets. The notebook-collaboration example uses pinned public CDNs for
this fallback, so its Vega output needs network access during browser
rendering. A self-contained offline bundle requires a separate asset decision.

The [compatibility probe](../../../examples/presentation-compatibility/README.md)
checks SVG, HTML, iframe HTML, mixed MIME bundles, and native Mermaid in real
JupyterLab and HTTP-served Quarto output. Its receipt records source hashes and
host versions. The semantic-tables checks cover actual diagrams, reading
controls, table colors, Bokeh state changes, and narrow-screen layout.
These checks establish the two supported hosts, not arbitrary frontends.
Keep the generated resource directory beside the HTML when serving the bundle.

References: [IPython display](https://ipython.readthedocs.io/en/stable/api/generated/IPython.display.html),
[JupyterLab notebooks](https://jupyterlab.readthedocs.io/en/stable/user/notebook.html),
[Quarto diagrams](https://quarto.org/docs/authoring/diagrams.html), and
[Quarto Jupyter widgets](https://quarto.org/docs/interactive/widgets/jupyter.html).

## Completion

Inspect changed display output in both supported hosts. Check meaning, output
order, reading controls, and layout at the intended widths. In JupyterLab,
confirm notebook trust and inspect the rendered output area. Use the
compatibility probe where it covers a changed display mechanism. Reuse unchanged
verification evidence when it still covers the relevant source, tools, and
hosts. Record the inspected hosts and any limits.
