# Project map: one mixed-stack executable architecture report

## Stage and authority

The report is in exploration. The file roles are stable, but the lesson can
still change as the architecture model improves.

Use these labels:

- [S] authored source. Edit and version it.
- [R] durable result or evidence. Regenerate it, then persist it.
- [P] browser deployment content.
- [I] disposable intermediate.
- [C] downloaded dependency, cache, or local tool state.

'ARCHITECTURE-GUIDE.md' owns the detailed conceptual model and primary-source
claims. 'DESIGN.md' owns the executable lesson contract. 'report.py' is the
only canonical notebook content. Do not edit the executed notebook, generated
lab HTML, or rendered report to change the lesson.

## Build and publication graph

~~~text
PROBLEM.md + ARCHITECTURE-GUIDE.md + DESIGN.md
                       |
                       v
                    report.py
              /         |          \
             v          v           v
 data/requests.csv + data/markouts.arrow + artifacts/ + comparison records
              \         |          /
                 report.executed.ipynb
                           |
                      Quarto render
                           |
               +-----------+-----------+
               |                       |
       report.rendered.html       report.static/
               |                       |
               +------ static HTTP ----+
                           |
             browser acceptance + RESULT.md
~~~

The three public operations are:

~~~text
report run --uv
  report.py -> report project environment -> executed notebook + generated labs

report render
  executed notebook -> Quarto without execution -> HTML + static files + inventory

static HTTP
  rendered HTML + artifacts + report.static + styles -> browser-only report
~~~

## Classified file tree

~~~text
charting-api-philosophy/
├── [S] PROBLEM.md
├── [S] ARCHITECTURE-GUIDE.md
├── [S] DESIGN.md
├── [S] report.py
├── [S] pyproject.toml
├── [S] uv.lock
├── [S] .python-version
├── [S] _quarto.yml
├── [S] styles/
│   ├── report.css
│   └── report-head.html
├── [S] evidence/architecture-source-notes.json
├── [S] README.md
├── [S] PROJECT-MAP.md
├── [S/R] RESULT.md
│
├── [I] data/requests.csv
├── [R/P] data/markouts.arrow       typed 1,600-trade deployment fixture
├── [I] report.ipynb                 unexecuted Jupytext projection
│
├── [R] report.executed.ipynb
├── [R] report.inventory.json
├── [R] evidence/
│   ├── comparison-records.json
│   ├── markout-data-receipt.json
│   ├── markout-size-tree.json
│   ├── mosaic-coordinator-contract.json
│   ├── report-inspection.json
│   ├── perspective-viewer-config.json
│   ├── browser-acceptance.json
│   ├── report-browser.png
│   └── report-render-receipt.json
│
├── [R/P] report.rendered.html
├── [R/P] report.inspect.html
├── [R/P] report.static/
├── [R/P] artifacts/
│   ├── bokeh-model-graph.html
│   ├── plotly-figure-protocol.html
│   ├── vega-runtime.html
│   ├── observable-d3-plot.html
│   ├── holoviews-lowering.html
│   ├── perspective-plugin-boundary.html
│   ├── markouts-ag-grid.html
│   ├── markouts-perspective.html
│   └── markouts-bokeh-histogram.html
│
├── [R] output/playwright/
│   ├── quarto-markouts.png
│   ├── jupyterlab-markout-tables.png
│   ├── quarto-markout-size-tree.png
│   └── jupyterlab-markout-size-tree.png
│
├── [C] .venv/
├── [C] .quarto/
├── [C] .playwright-cli/
└── [C] __pycache__/
~~~

The repository ignores the project environment, build state, browser session,
bytecode, and deterministic request CSV. The report recreates that CSV from
seed 20260823. The repository keeps `data/markouts.arrow` because it is the
HTTP deployment contract and shared data identity for the new section.

## Public repository boundary

The public example keeps the complete authoring bundle and the stable synthetic
Arrow fixture. It does not version executed notebooks, generated browser labs,
Quarto output, caches, screenshots, or browser logs. GitHub Actions creates
those files in a clean runner. The Pages artifact persists only the deployment
paths listed below.

This split keeps three authorities distinct:

~~~text
Git repository   authored inputs and locked dependencies
Actions runner   disposable execution and render materializations
Pages artifact   deployed HTML, sidecars, labs, styles, and Arrow data
~~~

## Authored source

These files contain human and agent decisions:

- 'PROBLEM.md' defines the question, limits, and predicted findings.
- 'ARCHITECTURE-GUIDE.md' defines the neutral vocabulary and library mappings.
- 'DESIGN.md' fixes the section order and edit/lower/inspect/verify contract.
- 'report.py' contains all executable prose, data preparation, trace code, and
  lab generators.
- 'architecture-source-notes.json' stores bounded primary-source research.
- 'pyproject.toml' declares dependency ranges; 'uv.lock' fixes the resolution.
- '_quarto.yml' and 'styles/' define publication policy and presentation.
- 'RESULT.md' records the accepted interpretation and verification result.

The former score rubric and short source-note file were removed. The current
architecture guide and source-note record supersede them.

## Imported, cloned, and downloaded content

No third-party repository was cloned into this project. No library source tree
is tracked here.

'uv' downloads Python packages into '.venv/'. That environment is about
970 MB and is not a report artifact. The shared uv cache stays outside this
project.

Quarto is an external build tool. The CLI records the observed renderer in
'report.inventory.json'. The project does not vendor Quarto.

Generated artifacts include third-party browser programs:

- 'vega-runtime.html' embeds generated Vega, Vega-Lite, and Vega-Embed code.
- The Bokeh and HoloViews labs embed BokehJS from the locked Python package.
- The Observable lab loads pinned Runtime, Inspector, Plot, and D3 modules from
  jsDelivr.
- The Plotly lab loads Plotly.js from its CDN.
- The Perspective lab loads pinned viewer, client, plugin, and Wasm resources
  from jsDelivr.
- The markout AG Grid and Bokeh artifacts load pinned Arrow JS from jsDelivr.
- The markout AG Grid artifact also loads AG Grid Community from jsDelivr.
- The Mosaic fragment loads Mosaic Core and SQL, DuckDB-Wasm, and Flechette
  from pinned jsDelivr packages. It converts the Arrow file to an IPC stream
  once because DuckDB-Wasm's insertion boundary accepts a stream.

These programs are dependencies or generated output. Do not edit them by hand.
Change 'report.py', dependency versions, or the deployment policy instead.

## Outputs

'report.ipynb' is an unexecuted Jupytext projection for notebook tools.
'report.executed.ipynb' is execution evidence. Neither notebook is the
authoring source.

'artifacts/' contains nine standalone browser labs. Six use path-based iframes.
The report mounts the three markout labs as host-native fragments in JupyterLab
and Quarto. Their standalone files remain direct-test and deployment outputs.
One host promise fetches `data/markouts.arrow`; each adapter receives a buffer
copy through the small URI adapter.

The Mosaic coordinator lab is an additional host-native fragment. It does not
replace the three standalone adapters. It inserts the Arrow data into one
DuckDB-Wasm table, owns one Mosaic Selection, and supplies three renderer
clients. AG Grid and Perspective request identical detail SQL, so Mosaic
consolidates both logical requests into one physical query. Bokeh requests a
48-row grouped histogram query.

'report.rendered.html' and 'report.static/' are the Quarto publication.
'report.inventory.json' connects their hashes to the source and notebook.

'evidence/comparison-records.json' stores data identity, versions, layer paths,
public runtime traces, and limits. 'mosaic-coordinator-contract.json' stores
the shared-plane invariants. 'browser-acceptance.json' stores the real browser
checks, including Mosaic query and row-count receipts.

'evidence/markout-size-tree.json' stores browser-observed markout DOM structure
and data-size diagnostics. `evidence/report-inspection.json` is the JSON-first
whole-report inspection record. `report.inspect.html` is its derived human
projection. None of these is a browser heap profile.

## Author workflow

Run these commands from this directory:

~~~bash
uv run --project ../.. report run "$(pwd)" --uv
uv run --project ../.. report render "$(pwd)"
uv run --project ../.. report inspect "$(pwd)" --render \
  > evidence/report-inspection.json
~~~

To inspect the accepted notebook output in JupyterLab, trust the generated
notebook and serve this directory as the Jupyter root:

~~~bash
uv run --project . jupyter trust report.executed.ipynb
jupyter-lab --no-browser --ServerApp.root_dir="$(pwd)"
~~~

The trust step permits the saved fragment scripts to run. It does not
start a Python callback server for the tables or chart.

For a CSS-only or Quarto-only change, skip 'report run' and render the accepted
notebook again.

For browser review:

~~~bash
uv run python -m http.server 8772 --bind 127.0.0.1
~~~

Open <http://127.0.0.1:8772/report.rendered.html>. Test all six isolation
iframes and all four host-native markout fragments after a source, dependency,
artifact, or deployment change.

## Deployment

Deploy these paths and preserve their relative layout:

~~~text
report.rendered.html
report.static/
styles/
artifacts/
data/markouts.arrow
~~~

The browser deployment does not need Python, Jupyter, Quarto, '.venv/', the
request CSV, the executed notebook, or the evidence directory. It does need
the Arrow fixture at the exact relative path shown above.

The current deployment is hosted, not offline. Observable, Plotly,
Perspective, AG Grid, Arrow JS, Mosaic, DuckDB-Wasm, and Flechette use remote
pinned browser resources.
Perspective also discovers viewer Wasm and either memory64 or wasm32 server
Wasm at runtime. Serve the project through static HTTP; do not use 'file://'.

For a controlled or offline deployment, vendor those browser modules and test
every dynamic worker and Wasm path. Treat that work as a consolidation task.

## Version-control policy

Version the complete source bundle:

~~~text
PROBLEM.md  ARCHITECTURE-GUIDE.md  DESIGN.md  report.py
pyproject.toml  uv.lock  .python-version
_quarto.yml  styles/  evidence/architecture-source-notes.json
README.md  PROJECT-MAP.md  RESULT.md
~~~

For this example, also persist the accepted notebook, JSON evidence, inventory,
browser capture, interactive labs, HTML, and static resources. They let a
reviewer inspect the result without rebuilding it.

Never version '.venv/', uv caches, Quarto state, Playwright session state,
'__pycache__/', or the deterministic CSV. Never hand-edit generated HTML,
notebook outputs, PNGs, inventory, or receipts.

## Maintainability boundary

'report.py' is now about 108 KiB. Keeping the narrative and orchestration in one
file is still useful during exploration. If another report needs the same lab
builders, move deterministic data and artifact emitters into a local package.
Keep the notebook section order in 'report.py'.

Do not add a split, CI system, or asset vendor step only for neatness. Add each
one when the project enters consolidation or when a second report proves reuse.
