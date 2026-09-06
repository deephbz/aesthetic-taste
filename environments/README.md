# Notebook environments

This directory owns the shared JupyterLab and analysis dependency groups.
Component projects own their additional kernel dependencies. uv manages the
Python environments; Jupyter manages kernel registrations. Quarto is a separate
prerequisite: make `quarto --version` work in the shell used to start JupyterLab.

Run these commands from the repository root.

## Host and default kernel

```sh
UV_PROJECT_ENVIRONMENT="$PWD/environments/.venv-lab" uv sync --project environments --only-group lab --frozen
UV_PROJECT_ENVIRONMENT="$PWD/environments/.venv-python3" uv sync --project environments --only-group default --frozen
environments/.venv-python3/bin/python -m ipykernel install \
  --prefix "$PWD/environments/.venv-lab" --name python3 --display-name "Python (analysis)" \
  --env QUARTO_PYTHON "$PWD/environments/.venv-python3/bin/python"
environments/.venv-lab/bin/jupyter lab --ServerApp.root_dir="$PWD"
```

The host and default kernel have separate environments. The `default` group
includes the shared `kernel` execution tools. Kernels inherit the host's PATH;
`QUARTO_PYTHON` selects the registered interpreter when Quarto executes Python.
Restart an affected kernel after changing its environment.

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
