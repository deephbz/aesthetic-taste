# Executable report CLI design

Stage: sharing. The interface is small and stable enough for public use. The
artifact schema remains pre-1.0 and can change with a version update.

## Problem and boundary

The tool turns editable Python research into saved, inspectable publication
artifacts. It does not manage live kernels, browser sessions, data stores, or
deployment infrastructure.

The public surface has four verbs:

```text
report new ROOT
report run ROOT (--uv | --python PATH)
report render ROOT [--quarto PATH]
report inspect ROOT [--render [PATH]]
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
separate. Parsed elements are structure proxies, not browser performance data.

## Failure and replacement rules

Each command reports one actionable error without a Python traceback. Failed
execution does not replace the last notebook. Failed rendering does not replace
the last HTML. Inspection returns a warning status and exit code 1 for stale,
unexecuted, or error-bearing artifacts.

Quarto resolution is explicit path, `PATH`, then the newest numeric install in
the supported local Quarto directory. Rendered resource paths and inventory
paths stay relative to the report root.

## Verification anchors

Unit tests cover creation, execution promotion, render preservation, sidecar
promotion, schema validation, drift detection, size dimensions, and the human
projection. CI runs tests and builds the package on Python 3.11 and 3.13. A
release smoke test must also execute one generated report and render it through
an installed Quarto binary.
