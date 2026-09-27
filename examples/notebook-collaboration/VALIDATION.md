# Notebook workflow validation

Date: 2026-09-27. Scope: the synthetic example and the maintained dependency
sets. This is bounded integration evidence, not a general renderer guarantee.

## Observed results

- The maintained Lab environment started with collaboration and nbmodel enabled,
  without Jupyter MCP. It used a separately registered analysis interpreter.
- A CLI-inserted cell appeared in the open browser. A browser edit from `42` to
  `43` reached a subsequent CLI read and shared-kernel evaluation.
- Selected-cell execution published table, Matplotlib, Bokeh, Vega, and Mermaid
  outputs. Direct Bokeh rendered after the notebook was trusted.
- A scratch kernel did not contain a shared variable. Its variable did not
  appear in the shared kernel. Kernel counts returned to their starting value
  after successful evaluation and after a Python exception.
- A Python exception produced a nonzero CLI exit status and retained error
  output. Moving a cell preserved its ID. Deleting it removed that ID from the
  next live read.
- The exported native notebook passed `nbformat.validate`. The derived Jupytext
  file preserved cell content modulo trailing whitespace. Native IDs remained
  in the notebook snapshot; importing Python is not an identity-preserving
  round trip.
- Native clean execution and Quarto rendering completed. The source notebook
  remained intact. The clean report inventory passed. Rendering a saved live
  snapshot reported unknown source freshness, as intended.
- Chrome showed the table, Matplotlib and Bokeh charts, Vega chart, and Mermaid
  diagram in the HTTP-served HTML. The final Vega loader produced no new
  console warnings or errors. It uses pinned AMD modules through Quarto's
  existing RequireJS loader to avoid anonymous-module conflicts.

## Reproduction and limits

Follow the [example instructions](README.md) and the maintained
[environment setup](../../environments/README.md). The host lock resolves
JupyterLab 4.6.3, collaboration 5.0.3, nbmodel server 0.2.9, and jupyter-bokeh
4.1.0. This run used the existing analysis kernel with Bokeh 3.9.2 and Quarto
1.10.18.

The notebook uses synthetic values A=3, B=7, and C=5 so both hosts can be checked
against the same expected values. The Vega HTML fallback requires network
access to its pinned public CDN modules. Python-backed widget callbacks and
generic widget export are outside this check.

The [collaboration guide](../../docs/notebook-collaboration.md#known-limits)
owns same-cell conflict and source/output race limits. This check does not add
atomic editing or stale-output prevention. Browser automation lost control of
one notebook tab during reload; native Chrome inspection still showed the
updated Bokeh output. Full reload recovery was not established by that check.
