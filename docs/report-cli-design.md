# Executable report CLI design

The implementation lives in `components/reporting/`. From the repository root,
run commands below with `uv run --project components/reporting --no-config report ...`.
See [repository setup](../README.md#use-reporting-tools).

Stage: sharing. The interface is small and stable enough for public use. The
artifact and browser-receipt schemas remain pre-1.0 and can change with a
version update.

## Problem and boundary

The tool turns editable Python research into saved, inspectable publication
artifacts. The `report notebook` command group also provides the small live
document surface needed for human-agent notebook collaboration. It does not
manage durable browser sessions, data stores, or deployment infrastructure.

The saved-report surface has six verbs:

```text
report new ROOT [--adopt]
report run ROOT (--uv | --python PATH) [--source PATH]
report render ROOT [--quarto PATH] [--notebook PATH]
report inspect ROOT [--render [PATH]]
report agent-view ROOT [--notebook PATH] [--code] [--limit CHARS]
report verify ROOT [--browser PATH] [--timeout SECONDS]
report notebook --server-json PATH [--notebook PATH] {status,read,edit,insert,move,delete,execute,eval,export} ...
```

`report --help`, `report inspect --help`, and `report verify --help` state the
observation boundary directly:

```text
inspect     what did we build?  saved artifacts and parsed HTML
agent-view  what does it say?   prose and compact output forms, by cell ID
verify      does it work?       one real Chromium execution
```

`report notebook` owns live notebook operations. Its detailed options and
structured output are part of the command help. The stable responsibilities
and operator limits are documented in the [live notebook collaboration
guide](notebook-collaboration.md):
identify the active document and kernel, read and edit stable cell IDs, execute
selected cells in a shared or scratch kernel, and export either a native
notebook snapshot or a Jupytext projection. Keep connection credentials out of
normal output.

During a live session, the `.ipynb` document is the editing authority. The
exported `.py` file is a derived review and build input. Existing `report run`
and `report render` behavior remains available for saved report projects. The
`--source` and `--notebook` options select native notebook inputs while
retaining source-hash checks and promotion-on-success rules.

## Artifact model

One report owns one flat root. Fixed names remove a second report manifest:

```text
report.py                  default authoritative Jupytext source
pyproject.toml             report Python project and dependencies
uv.lock                    resolved Python environment
_quarto.yml                no-execution publication policy
reading-navigation.html    editable reading-navigation source
lib/                       optional local report modules
report.executed.ipynb      executed display state
report.rendered.html       HTTP publication
report.static/             HTTP sidecar resources
report.inventory.json      structural and provenance inventory
report.inspect.html        optional human inspection projection
report.verify.json         latest real-browser verification receipt
report.verify.png          latest initial-viewport browser evidence
```

`new` accepts only a missing or empty root. `--adopt` adds the missing inputs
to an existing study and keeps every existing file. It seeds the reading profile from
`executable_reports.presentation`: format settings live in the notebook's raw
frontmatter, and `reading-navigation.html` is a report-owned source snapshot.
The defaults include contents, section highlighting, and scroll progress.
Existing reports are not overwritten when the package changes. The
[presentation guide](../.agents/skills/report-presentation/SKILL.md) describes customization and reuse.

`run` converts and executes through
temporary notebooks, records source and interpreter identity, then promotes
the result only when the source hash is unchanged. `--source` selects a
Jupytext source or a native `.ipynb` inside the report root; it defaults to
`report.py`. `--uv` uses the report project environment. `--python` uses one
explicit interpreter. A Jupytext cell marked `# %% id="name"` keeps `name` as
its native cell ID; `run` rejects a duplicate or invalid ID. Unmarked cells get
a fresh ID on each conversion.

`render` calls Quarto with `--no-execute`. It preserves the executed notebook
hash, moves sidecars to `report.static/`, and records hashes, output MIME data,
serialized sizes, and parsed HTML structure in the inventory. `--notebook`
selects a saved `.ipynb` inside the report root; it defaults to
`report.executed.ipynb`.

For a live notebook handoff, export the reviewed notebook snapshot before the
clean run. `render` consumes saved notebook outputs and does not execute the
live kernel. JupyterLab trust controls browser execution of rich notebook MIME
output; the static HTML bundle still requires its own HTTP and browser check.

`inspect` validates the inventory schema and checks artifact drift. JSON is the
default authority for agents. `--render` derives a human HTML view from the
same inspection record. Byte counts, element counts, and execution counts stay
separate. Parsed elements are structure proxies, not browser runtime evidence.

`agent-view` prints the agent view of the saved notebook: markdown prose whole,
then each output's `text/plain` (else `text/markdown`) form under its stable
cell ID, cut at `--limit` characters. An output with only rich forms prints a
`no compact form` stub. It reads no HTML and runs nothing.

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
