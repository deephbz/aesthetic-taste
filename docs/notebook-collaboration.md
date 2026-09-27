---
purpose: Define the supported human-agent workflow for live Jupyter notebook research.
owns: Live notebook authority, selected-cell execution, shared and scratch kernels, and the one-way Jupytext export.
does-not-own: Static report guarantees, data computation or caching, deployment, or Marimo workflows.
stage: consolidation
status: active
---

# Live notebook collaboration

Use this workflow for exploratory research where a human and an agent inspect
the same notebook and kernel. The live notebook is the collaboration surface.
The saved notebook is the durable record. A Jupytext file is a derived review
projection.

```text
human in JupyterLab ─┐
                     ├─ live .ipynb document ── saved .ipynb
agent: report notebook ┘             │
                                     └─ export ── derived .py
```

The notebook owns the current cell order, stable cell IDs, outputs, and shared
execution state. Agents must address cells by ID when the operation supports
it. A line range in a large `.py` projection is not a cell identity.

## Session model

Start a session from the notebook that the human has opened in JupyterLab.
Select the intended analysis kernel and trust the notebook before displaying
browser-executable output. The JupyterLab **Trust Notebook** command is part of
the setup for local research notebooks. A trusted notebook allows saved
JavaScript and rich MIME output to run in the browser; only trust a notebook
whose source and outputs are understood.

Use the existing repository environment and kernel registrations described in
the [environment guide](../environments/README.md). The host supplies the
JupyterLab collaboration layer. The analysis kernel supplies Python and the
libraries used by the report. Add renderer packages only when the report uses
them. The base workflow defines no widget dependency or widget parity promise.
A report that uses widgets must declare and verify both host paths. Bokeh
notebook output requires the matching `jupyter_bokeh` frontend and a trusted
notebook.

The agent uses the `report notebook` command group. Each live operation needs
the server credential JSON and the server-relative notebook path before the
operation, for example:

```text
report notebook --server-json SERVER.json --notebook report.ipynb status
```

The exact options are owned by `report notebook --help`.

| Command | Responsibility |
| --- | --- |
| `status` | Report the server, notebook, session, configured kernel, and connection state. |
| `read` | Read cell IDs, source, outputs, and execution errors from the live document. |
| `edit` | Replace one cell's source. Use the sibling `insert`, `move`, and `delete` operations for structural changes. |
| `insert` / `move` / `delete` | Change cell structure while preserving native IDs where the operation supports it. |
| `execute` | Execute selected cells in the shared kernel and publish their outputs. |
| `eval` | Perform bounded inspection or scratch evaluation with an explicitly chosen kernel. |
| `export` | Write an `.ipynb` snapshot or Jupytext `.py` projection from a consistent live snapshot. |

The command help owns option spelling and transport details. `status` reports
configured kernel metadata; it does not prove which interpreter runs inside the
kernel process. Use shared evaluation to inspect `sys.executable` when that
distinction matters. Keep credentials, tokens, and raw connection URLs out of
normal output. Use structured output when another agent or script consumes the
result.

## Human-agent loop

1. The human opens the notebook, chooses the analysis kernel, and trusts the
   notebook when rich output needs browser execution.
2. The agent runs `report notebook status` and `read` before editing. It
   records the cell IDs and reads the current source before replacing a cell.
3. The agent edits one cell or one independent section. The human sees the
   change in JupyterLab through the shared document model.
4. The agent executes only the changed cells when shared state is intentional.
   The human can also execute a cell from JupyterLab. Both participants inspect
   the same output cell.
5. The agent uses `eval` with a scratch kernel for experiments that must not
   mutate the shared namespace. It uses the shared kernel when debugging an
   existing variable, API result, or renderer state is the goal.
6. The agent reads the output and errors after execution. A successful Python
   response proves execution only. Visible chart or diagram rendering needs a
   host check in JupyterLab.
7. Before a saved report build, the agent exports a reviewed `.py` projection
   or passes the native notebook to `report run --source`. It then uses
   `report render` with saved outputs. The export is an explicit handoff. It
   does not silently overwrite a live
   notebook or reload a `.py` file into JupyterLab.

Keep sections independently executable where practical. Put shared imports and
configuration in the setup section. Make section inputs and outputs visible so
the agent can rerun one section without reconstructing hidden state.

If the JupyterLab server, kernel, or collaboration extension restarts, refresh
or reconnect the browser notebook session before rerunning cells. An old UI
connection can retain stale document state.

## Static delivery boundary

Live collaboration and publication are separate operations. The notebook may
contain temporary exploration and a stateful kernel. A saved report build must
use a reviewed source snapshot and a clean execution path. `report run` records
the executed notebook. `report render` consumes saved notebook outputs with
Quarto's no-execute policy. The [report contract](report-contract.md) owns
notebook-to-HTML meaning and publication guarantees.

Use [report delivery](../.agents/skills/report-delivery/SKILL.md) for the
handoff and [report presentation](../.agents/skills/report-presentation/SKILL.md)
for MIME, Mermaid, Bokeh, and HTML host checks.

## Known limits

These limits are accepted in the consolidation stage and must remain visible
to operators:

- Concurrent replacement of the same cell has no general merge guarantee.
  Reread the cell after another participant edits it. Reapply the intended
  change against the current source when needed.
- A cell can finish execution after its source changes. An output can therefore
  belong to an earlier source revision. Read source and output together and
  rerun after a source change when the distinction matters.
- Selective execution preserves kernel state, so an edited cell can depend on
  stale variables from earlier execution. Restart the kernel and run the
  required setup when state provenance is unclear.
- Notebook trust controls browser execution of rich output. Trust does not
  prove analytical correctness, and a MIME bundle in the document does not
  prove that a renderer displayed it.
- The workflow does not provide expensive computation caching or a Marimo
  compatibility layer. Keep those concerns in their own design work.

The CLI may report revisions, execution counts, and output metadata to make
these cases inspectable. Such metadata helps diagnosis; it does not turn
same-cell edits or stateful execution into transactions.

## Completion

A live collaboration change is complete when the intended cell source is
visible in JupyterLab, the selected shared or scratch execution has a readable
result, and the agent has checked the output against the current source. A
publication change is complete only after the saved notebook, rendered HTML,
and requested browser checks pass their respective receipts.
