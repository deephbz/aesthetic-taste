# Charting API philosophy

An exploration-stage architecture lesson and a concrete example of rendering
and serving a report without an application server. It traces authoring APIs
through runtime state to pixels, with browser labs and one shared Arrow dataset.

[DESIGN.md](DESIGN.md) owns the lesson's intent and constraints.
The [architecture guide](research/ARCHITECTURE-GUIDE.md) owns the source-linked
comparison; [problem](research/PROBLEM.md) and [result](research/RESULT.md) retain
research context and accepted evidence. `report.py` is the executable source.

```text
Python source + data → executed notebook + evidence → Quarto HTML bundle
                                                        ↓
                                                  static HTTP host
                                                        ↓
                                              browser JavaScript + Wasm
```

Python executes during generation. The published report needs static HTTP and
network access for CDN dependencies. It needs no running Python kernel or
application server. This is not an offline bundle.

## Artifact ownership

- [S] Authored source: edit and version `report.py`, design/research documents,
  styles, environment definitions, and `stage_site.py`.
- [R] Durable result or evidence: regenerate, then persist the executed notebook,
  machine receipts, rendered report, and dataset. Git retains the accepted
  `data/markouts.arrow` fixture and selected evidence; CI persists its publication
  as a workflow artifact. Generated files are not all versioned in Git.
- [P] Browser deployment content: HTML, browser resources, styles, runtime artifacts,
  and Arrow data selected by [stage_site.py](stage_site.py). This is a projection
  of source and results, not another analytical authority.
- [I] Disposable intermediate: staging directories and temporary rendering files.
- [C] Downloaded dependency, cache, or local tool state: virtual environments,
  package caches, and downloaded browser dependencies.

Keep reusable source in the repository, task scaffolding in the project workspace,
and durable distributed results in shared artifact storage. Temporary directories
are scratch. `.gitignore` controls Git inclusion; it does not define durability.
The staging script owns the exact publication file list.

## Run and serve

From this directory:

```sh
uv run --project ../../components/reporting --no-config report run "$(pwd)" --uv
uv run --project ../../components/reporting --no-config report render "$(pwd)"
uv run --project ../../components/reporting --no-config report inspect "$(pwd)" --render > evidence/report-inspection.json
uv run --project ../../components/reporting --no-config --with playwright report verify "$(pwd)"
python3 -m http.server 8772 --bind 127.0.0.1
```

Open [the report](http://127.0.0.1:8772/report.rendered.html) or
[artifact inspection](http://127.0.0.1:8772/report.inspect.html).
The verification command writes `report.verify.json` and `report.verify.png`.
CI executes, renders, inspects, and verifies before staging for GitHub Pages.

From the repository root, `python3 examples/charting-api-philosophy/stage_site.py`
creates `_site/` after generation. The destination must be absent.
For notebook use, follow the shared [Jupyter setup](../../environments/README.md),
trust `report.executed.ipynb`, and open it in JupyterLab. The browser adapters
resolve the same Arrow file through Jupyter's `/files/` route.
