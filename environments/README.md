# Notebook environments

This directory owns the shared JupyterLab and analysis dependency groups.
Component projects own their additional kernel dependencies. uv manages the
Python environments; Jupyter manages kernel registrations. Quarto is a separate
prerequisite: make `quarto --version` work in the shell used to start JupyterLab.

The `lab` group contains the host-side collaboration and display layer:
`jupyter-collaboration`, `jupyter-server-nbmodel`, `jupyter-bokeh`, and
`jupyterlab-widgets`. `jupyter-bokeh` pulls `ipywidgets` into the host because
its renderer requires the Jupyter widget manager. The analysis groups do not
add `ipywidgets`: generic widget state and Python callbacks are not part of the
verified static HTML contract.

Run these commands from the repository root.

## Host and default kernel

```sh
UV_PROJECT_ENVIRONMENT="$PWD/environments/.venv-lab" uv sync --project environments --only-group lab --frozen
UV_PROJECT_ENVIRONMENT="$PWD/environments/.venv-python3" uv sync --project environments --only-group default --frozen
environments/.venv-python3/bin/python -m ipykernel install \
  --prefix "$PWD/environments/.venv-lab" --name python3 --display-name "Python (analysis)" \
  --env QUARTO_PYTHON "$PWD/environments/.venv-python3/bin/python"
```

The host and default kernel have separate environments. The `default` group
includes the shared `kernel` execution tools. Kernels inherit the host's PATH;
`QUARTO_PYTHON` selects the registered interpreter when Quarto executes Python.
Restart an affected kernel after changing its environment.

## Live notebook collaboration

The collaboration host and the analysis kernel are separate. Follow the host
and kernel setup above before starting a live session.

The tracked [`launch.py`](collaboration/launch.py) owns the server setup. It
creates isolated Jupyter state, copies
[`page_config.json`](collaboration/page_config.json), enables RTC, nbmodel, and
JupyterLab, and writes a mode-0600 `server.json` under the runtime directory.
It disables the two built-in cell executors that would otherwise race with
nbmodel. It keeps the ordinary file browser enabled and does not load MCP.
Run it with a runtime directory outside the notebook root:

```sh
runtime_dir="${TMPDIR:-/tmp}/aesthetic-taste-jupyter"
environments/.venv-lab/bin/python environments/collaboration/launch.py \
  --root-dir "$PWD" \
  --runtime-dir "$runtime_dir" \
  --port 8896
```

The launcher prints a token-free Lab URL and the connection record path. Keep
the token in that ignored record. Do not place it in a notebook, repository
config, or shell history. Existing kernels registered under the Lab host
prefix remain discoverable.

Install the optional agent client when using the live notebook CLI:

```sh
uv sync --project components/reporting --extra notebook
uv run --project components/reporting --extra notebook report notebook \
  --server-json "$runtime_dir/server.json" \
  --notebook report.ipynb status
```

Trust the notebook in JupyterLab before displaying JavaScript-backed rich
output such as direct Bokeh plots.

## Component kernels

For example, register the semantic-tables project's independent environment:

```sh
uv sync --project examples/semantic-tables --frozen
examples/semantic-tables/.venv/bin/python -m ipykernel install \
  --prefix "$PWD/environments/.venv-lab" --name semantic-tables --display-name "Python (semantic tables)" \
  --env QUARTO_PYTHON "$PWD/examples/semantic-tables/.venv/bin/python"
```

Use the same commands with `examples/charting-api-philosophy` and a matching
kernel name for that report. Each kernel project must include `ipykernel`.
A component can serve several related examples; it does not need one kernel
per notebook.

## Change dependencies or registrations

```sh
uv add --project environments --group default seaborn
uv remove --project environments --group default seaborn
uv add --project examples/semantic-tables PACKAGE
environments/.venv-lab/bin/jupyter kernelspec list
environments/.venv-lab/bin/jupyter kernelspec remove KERNEL_NAME
```

After changing dependencies, repeat the relevant sync command. uv updates the
lock with `add` and `remove`; after editing a manifest by hand, run `uv lock
--project PATH`. `--frozen` installs the existing lock without resolving it again.

Additional shared kernels can select another dependency group with
`--only-group GROUP` and a separate `UV_PROJECT_ENVIRONMENT`. Groups share a
lock; use independent component projects when their dependency lifecycles or
Python requirements differ.

Kernel registrations and virtual environments are generated local state. Inspect
the path shown by `kernelspec list` before removing a registration. Removing a
registration does not remove its environment directory or stop a running kernel.
