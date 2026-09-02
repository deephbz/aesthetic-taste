# Aesthetic Taste

Aesthetic Taste is a small package for inspectable research-report tools. Its
first tool is `report`, a command-line workflow from Jupytext source to an
executed notebook, Quarto HTML, a machine-readable artifact inventory, and an
optional real-browser verification receipt.

## Install

```sh
uv tool install git+https://github.com/deephbz/aesthetic-taste.git
report --help
```

Quarto is a separate system dependency. A generated report project records its
Python execution dependencies in its own `pyproject.toml` and `uv.lock`.

Browser verification is optional. Install the Playwright Python package in the
same tool environment and either use an existing Chrome/Chromium executable or
install Playwright Chromium:

```sh
uv tool install --with playwright git+https://github.com/deephbz/aesthetic-taste.git
uvx playwright install chromium
```

## Use

```sh
report new my-report
report run my-report --uv
report render my-report
report inspect my-report
report inspect my-report --render
report verify my-report
```

`report inspect` answers **what did we build?** It checks saved artifacts,
hashes, notebook outputs, sizes, and parsed HTML without starting a browser.
`report verify` answers **does it work?** It serves the static bundle over
loopback HTTP, loads it in headless Chromium, and writes `report.verify.json`
plus `report.verify.png`.

The verification receipt records runtime errors, failed resources,
high-confidence layout failures, detected view roots, and an optional
`window.__REPORT_VERIFY__` result. Every failure points to small pre-1.0 Python
diagnostic helpers that can reopen the report, inspect one selector, capture a
targeted screenshot, or record a Playwright trace.

Read [the report contract](docs/report-contract.md) for the report seen from
outside (deployment shape, data and state authority, notebook-to-web parity),
[report authoring](docs/report-authoring.md) for the structure of report code
and the contract of reusable analysis components, [the CLI design](docs/report-cli-design.md)
for tool behavior, and [the collaboration guide](docs/SKILL.md) for the live
authoring and HTTP serving loop.

The parts are at different stages. The CLI is in sharing. The report contract
is in consolidation. Report authoring is in shaping. The example report is in
exploration. Each document states its own stage at the top.

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
it with `report`, renders and verifies it, and deploys the result to
[GitHub Pages](https://deephbz.github.io/aesthetic-taste/).
