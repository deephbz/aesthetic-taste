# Aesthetic Taste

Aesthetic Taste is a small package for inspectable research-report tools. Its
first tool is `report`, a command-line workflow from Jupytext source to an
executed notebook, Quarto HTML, and a machine-readable artifact inventory.

## Install

```sh
uv tool install git+https://github.com/deephbz/aesthetic-taste.git
report --help
```

Quarto is a separate system dependency. A generated report project records its
Python execution dependencies in its own `pyproject.toml` and `uv.lock`.

## Use

```sh
report new my-report
report run my-report --uv
report render my-report
report inspect my-report
report inspect my-report --render
```

`report inspect` writes JSON to standard output. `--render` also creates the
human projection `report.inspect.html` from that same inspection record.

Read [the principles](docs/principles.md) for the report contract, [the CLI
design](docs/report-cli-design.md) for tool behavior, and [the collaboration
guide](docs/SKILL.md) for the live authoring and HTTP serving loop.

## Develop

```sh
uv sync
uv run python -m unittest discover -s tests -v
uv build
```

This repository contains only the reusable CLI, its tests, and its governing
documents, plus reproducible example source bundles. Generated report artifacts
stay outside Git history.

## Example

[`examples/charting-api-philosophy`](examples/charting-api-philosophy) contains
the source for the API-to-pixels architecture report. GitHub Actions rebuilds
it with `report`, renders it with Quarto, and deploys the result to
[GitHub Pages](https://deephbz.github.io/aesthetic-taste/).
