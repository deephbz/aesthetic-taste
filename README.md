# Aesthetic Taste

Aesthetic Taste is a small package for inspectable research-report tools. Its
first tool is `report`, a command-line workflow from Jupytext source to an
executed notebook, Quarto HTML, a machine-readable artifact inventory, and an
optional real-browser verification receipt.

## Use reporting tools

Clone the repository and run these commands from its root. uv installs the local
reporting component into its own environment; no published package is needed.

```sh
git clone https://github.com/deephbz/aesthetic-taste.git
cd aesthetic-taste
uv sync --project components/reporting --locked --no-config
uv run --project components/reporting --no-config report --help
```

Quarto is a separate system dependency. Each report project owns its execution
dependencies in its own `pyproject.toml` and `uv.lock`.

```sh
uv run --project components/reporting --no-config report new my-report
uv run --project components/reporting --no-config report run my-report --uv
uv run --project components/reporting --no-config report render my-report
uv run --project components/reporting --no-config report inspect my-report --render
uv run --project components/reporting --no-config --with playwright report verify my-report
```

Browser verification is optional. The last command adds Playwright to the run
environment. Use an installed Chrome/Chromium browser, or install Chromium with
`uv run --project components/reporting --no-config --with playwright playwright install chromium`.

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
for tool behavior, [presentation defaults](docs/report-presentation.md) for reusable
reading navigation and portable display formats, and [the collaboration guide](docs/SKILL.md) for the live
authoring and HTTP serving loop.

The parts are at different stages. The CLI is in sharing. The report contract
is in consolidation. Report authoring is in shaping. The example report is in
exploration. Each document states its own stage at the top.

## Develop

```sh
uv sync --project components/reporting --locked --no-config
uv run --project components/reporting --no-config python -m unittest discover -s components/reporting/tests -v
```

Reusable report code and tests live in [components/reporting](components/reporting/).
Each component owns its Python project; the repository root has no Python project. Design guidance
lives in `docs/`, while research prototypes and reproducible source bundles live
in `examples/`. Generated report artifacts
stay outside Git history.

## Example

[`examples/charting-api-philosophy`](examples/charting-api-philosophy) contains
the source for the API-to-pixels architecture report. GitHub Actions rebuilds
it with `report`, renders and verifies it, and deploys the result to
[GitHub Pages](https://deephbz.github.io/aesthetic-taste/).
