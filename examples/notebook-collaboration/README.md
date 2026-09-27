---
purpose: Provide a small synthetic notebook for the live collaboration and saved delivery workflow.
scope: Exercise cell-aware editing, selected-cell execution, rich output, and native notebook handoff; data backend design is out of scope.
stage: consolidation
status: active
---

# Notebook collaboration example

This example is a small, self-contained notebook for a human and an agent to
edit together. It includes a table, Matplotlib, direct Bokeh, Vega-Lite, and a
Mermaid diagram. The cells have stable IDs so the live notebook commands can
address them without counting lines in a derived `.py` file.

Open [report.ipynb](report.ipynb) in JupyterLab, select the intended analysis
kernel, and use **Trust Notebook** before displaying browser-executable output.
The Bokeh cell needs the host's matching `jupyter_bokeh` renderer. The Vega
cell provides native Vega MIME for JupyterLab and an equivalent HTML fallback
for Quarto. The fallback loads pinned public CDN assets, so Vega browser
rendering needs network access. The example defines no general widget stack.

From the repository root, inspect the command surfaces before running the
handoff. The help output owns the exact input and output option spelling:

```sh
uv run --project components/reporting --no-config --extra notebook report notebook --help
uv run --project components/reporting --no-config report run --help
uv run --project components/reporting --no-config report render --help
```

Use the server credential file and the server-relative notebook path with the
live commands:

```sh
uv run --project components/reporting --no-config --extra notebook report notebook \
  --server-json SERVER.json --notebook report.ipynb status
uv run --project components/reporting --no-config --extra notebook report notebook \
  --server-json SERVER.json --notebook report.ipynb read
```

Use `edit` and `execute` for a selected live cell, and `eval --scratch` for
isolated work. Export a reviewed native snapshot or Jupytext projection:

```sh
uv run --project components/reporting --no-config --extra notebook report notebook \
  --server-json SERVER.json --notebook report.ipynb export \
  --format py --output /tmp/collaborative-report.py
uv run --project components/reporting --no-config --extra notebook report notebook \
  --server-json SERVER.json --notebook report.ipynb export \
  --format ipynb --output /tmp/collaborative-report.ipynb
```

Pass the native notebook to the clean `report run` path:

```sh
uv run --project components/reporting --no-config report run examples/notebook-collaboration \
  --source report.ipynb --python PATH_TO_ANALYSIS_PYTHON
uv run --project components/reporting --no-config report render examples/notebook-collaboration \
  --notebook report.executed.ipynb
```

Then inspect and verify the resulting bundle with the normal delivery commands.

The [collaboration guide](../../docs/notebook-collaboration.md) defines the
source-of-truth boundary, trust rule, shared versus scratch execution, and
accepted same-cell and stale-output limits.

See [validation results and limits](VALIDATION.md) for the tested workflow.
