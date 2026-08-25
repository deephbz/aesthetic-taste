# Executable report CLI design

Stage: sharing. The interface is small and stable enough for public use. The
artifact and browser-receipt schemas remain pre-1.0 and can change with a
version update.

## Problem and boundary

The tool turns editable Python research into saved, inspectable publication
artifacts. It does not manage live kernels, durable browser sessions, data
stores, or deployment infrastructure.

The public surface has five verbs:

```text
report new ROOT
report run ROOT (--uv | --python PATH)
report render ROOT [--quarto PATH]
report inspect ROOT [--render [PATH]]
report verify ROOT [--browser PATH] [--timeout SECONDS]
```

`report --help`, `report inspect --help`, and `report verify --help` state the
observation boundary directly:

```text
inspect  what did we build?  saved artifacts and parsed HTML
verify   does it work?       one real Chromium execution
```

## Artifact model

One report owns one flat root. Fixed names remove a second report manifest:

```text
report.py                  authoritative Jupytext source
pyproject.toml             report Python project and dependencies
uv.lock                    resolved Python environment
_quarto.yml                publication policy
lib/                       optional local report modules
report.executed.ipynb      executed display state
report.rendered.html       HTTP publication
report.static/             HTTP sidecar resources
report.inventory.json      structural and provenance inventory
report.inspect.html        optional human inspection projection
report.verify.json         latest real-browser verification receipt
report.verify.png          latest initial-viewport browser evidence
```

`new` accepts only a missing or empty root. `run` converts and executes through
temporary notebooks, records source and interpreter identity, then promotes
the result only when the source hash is unchanged. `--uv` uses the report
project environment. `--python` uses one explicit interpreter.

`render` calls Quarto with `--no-execute`. It preserves the executed notebook
hash, moves sidecars to `report.static/`, and records hashes, output MIME data,
serialized sizes, and parsed HTML structure in the inventory.

`inspect` validates the inventory schema and checks artifact drift. JSON is the
default authority for agents. `--render` derives a human HTML view from the
same inspection record. Byte counts, element counts, and execution counts stay
separate. Parsed elements are structure proxies, not browser runtime evidence.

## Browser verification

`verify` starts one transient loopback HTTP server and one headless Chromium
context. It performs bounded, high-signal checks:

- navigation status and completed document loading;
- unhandled JavaScript errors, console errors, dialogs, and page crashes;
- failed requests, HTTP error responses, pending requests, and broken images;
- document overflow and zero-size declared views;
- visible Canvas drawing-buffer size and SVG viewBox sanity;
- detected Perspective, AG Grid, Bokeh, Plotly, Vega, Canvas, custom-element,
  and `[data-report-view]` roots;
- optional report-owned checks from `window.__REPORT_VERIFY__`.

The local server supports static-resource MIME types and single HTTP byte-range
requests so browser query engines can inspect Arrow, Wasm, and large analytical
files through normal static transport. The default screenshot covers one fixed
initial viewport. The command does not claim automated visual taste judgment;
agents should read the screenshot when pixels matter.

Warnings remain visible in the receipt but do not fail the command. Runtime,
resource, navigation, declared-view, and report-owned errors return exit code 1.
The command always attempts to write a bounded JSON receipt, including setup
failures such as a missing Playwright package or browser executable.
Verification receipts and screenshots are diagnostic evidence, not publication
artifacts by default; exporting them is an explicit release decision.

A report may expose a small semantic acceptance hook:

```javascript
window.__REPORT_VERIFY__ = async () => ({
  status: "passed",
  checks: [
    { name: "trade rows", status: "passed" }
  ]
});
```

The generic verifier owns browser health and layout checks. The report hook owns
application-specific facts such as row counts, selected state, or linked-view
invariants.

## Agent diagnostics

The receipt is the supported interface. Each problem identifies its category,
severity, selector when available, evidence, and diagnostic API. The receipt
also includes a copy-ready call to:

```python
from executable_reports.verification import diagnose_problem
```

The following Python helpers are intentionally internal and pre-1.0:

```text
serve_report       start the same loopback static transport
browser_session    open the report and expose the live Playwright page
inspect_page       repeat the generic runtime/layout probe
inspect_elements   extract geometry, styles, text, and bounded outer HTML
inspect_overflow   run a whole-document overflow scan only during diagnosis
diagnose_report    capture one selector, screenshot, events, and optional trace
diagnose_problem   start directly from one receipt problem
```

These helpers reduce incident startup cost. They do not promise API stability;
agents may inspect their source when deeper library-specific state is required.

## Failure and replacement rules

Each command reports one actionable error without a Python traceback. Failed
execution does not replace the last notebook. Failed rendering does not replace
the last HTML. Inspection returns a warning status and exit code 1 for stale,
unexecuted, or error-bearing artifacts.

Verification promotes a new receipt and screenshot atomically where practical.
If no current screenshot exists, an older screenshot is removed so evidence is
not silently stale. Quarto resolution is explicit path, `PATH`, then the newest
numeric install in the supported local Quarto directory. Rendered resource
paths and inventory paths stay relative to the report root.

## Verification anchors

Unit tests cover creation, execution promotion, render preservation, sidecar
promotion, schema validation, drift detection, size dimensions, human
projection, verification receipt classification, help boundaries, range-aware
static serving, and diagnostic bootstrap text. CI runs tests and builds the
package on Python 3.11 and 3.13. The Python 3.13 job also runs one real-browser
smoke report. The published charting example runs `report verify` before its
Pages artifact is staged.
