# Report presentation

Stage: consolidation. This guide owns presentation choices and their limits.
The [report contract](report-contract.md) owns observable outcomes.
Supported hosts are JupyterLab/notebooks and HTTP-served HTML bundles.

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
is a real requirement. Normal notebook trust rules still apply.

The [compatibility probe](../examples/presentation-compatibility/README.md)
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
