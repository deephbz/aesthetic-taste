# Charting API philosophy

An exploration-stage executable architecture lesson. It starts from
Matplotlib's object-oriented model, then traces Vega, Observable, D3, Plot,
Bokeh, Plotly, HoloViews, Datashader, Perspective, and AG Grid from data to
pixels or table DOM.

Artifact chain:

```text
PROBLEM.md + ARCHITECTURE-GUIDE.md + DESIGN.md
                       |
                    report.py
                   /    |    \
            evidence  artifacts  executed notebook
                   \    |    /
                 Quarto HTML
```

`report.py` is the canonical executable source. The notebook is executed
evidence. The HTML is a static publication projection.

The public repository versions the reproducible source bundle, not generated
notebooks or HTML. GitHub Actions executes this source with the packaged
`report` CLI, renders through Quarto, and deploys the static publication to
GitHub Pages. The workflow artifact is the persisted publication result.

Read `PROJECT-MAP.md` for the complete authored/generated/downloaded file map,
the version-control policy, and the exact static deployment boundary.

Read `ARCHITECTURE-GUIDE.md` for the detailed source-linked model. The rendered
report is its executable companion. It includes nine kernel-free browser labs
and bounded public runtime traces. One section projects the same 1,600-trade
Arrow IPC file through pandas, AG Grid, Perspective, and a Bokeh histogram.
The section includes a hierarchical DOM and data-size receipt. Its three
browser views mount directly in the host DOM and share one Arrow request.
The next section keeps those independent adapters intact, then adds a Mosaic
coordinator lab. One DuckDB-Wasm table supplies linked AG Grid, Perspective,
and Bokeh clients through shared filter state and coordinated SQL queries.

## Run it

From this directory:

```bash
uv run --project ../.. report run "$(pwd)" --uv
uv run --project ../.. report render "$(pwd)"
uv run --project ../.. report inspect "$(pwd)" --render \
  > evidence/report-inspection.json
uv run python -m http.server 8772 --bind 127.0.0.1
```

Open <http://127.0.0.1:8772/report.rendered.html>. Use static HTTP because the
Perspective example fetches JavaScript and Wasm modules. It does not need a
Python server after publication.

Open <http://127.0.0.1:8772/report.inspect.html> for the human inspection
projection. `evidence/report-inspection.json` is its machine authority.

For the equivalent JupyterLab view, trust the executed notebook and serve this
project as the Jupyter root:

```bash
uv run --project . jupyter trust report.executed.ipynb
jupyter-lab --no-browser --ServerApp.root_dir="$(pwd)"
```

Open `report.executed.ipynb`. The browser adapters resolve the same stable
`data/markouts.arrow` identity through Jupyter's `/files/` route.

Read `DESIGN.md` for the executable lesson contract. `RESULT.md` records the
accepted local verification result. CI regenerates machine evidence before it
publishes the report.
