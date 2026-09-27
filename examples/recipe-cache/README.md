# Recipe cache

Purpose: reuse the results of slow computation steps without stale results.
Scope: explicit persistence of individual Python function calls, keyed by what
the result depends on. Status: exploration. It passes the end-to-end tests
below. It has not yet run on a real research pipeline.

Invariants:

- Persistence is explicit. Only functions wrapped by `Store.persist` are stored.
- A stored result is reused only when all key parts are unchanged.
- A failed or interrupted computation publishes nothing.
- A call returns the value read back from storage, so reuse and first computation
  return the same thing.

Non-goals: scheduling, parallel or distributed execution, partition-level
rebuilds, and dependencies on DatasetFrame or another semantic layer. DuckDB and
other engines connect through `register_codec`, or by returning a Polars frame.

## Use

```python
from recipe_cache import File, Store

store = Store("/nfs/me/.recipe-cache")          # share it between kernels and scripts

@store.persist
def join_fills(fills: File, quotes: File, tolerance_ms: int) -> pl.DataFrame:
    ...                                          # read inputs through their File paths

joined = join_fills(File("/nfs/fills.parquet"), File("/nfs/quotes/"), tolerance_ms=50)
summary = summarize(joined, by="sym")           # a persisted result can be passed on

join_fills.explain(...)   # hit or miss, with reasons, without computing
join_fills.refresh(...)   # recompute and replace
join_fills.audit(...)     # recompute and compare bytes with the stored result
```

Each call prints one line to standard error:

```text
recipe-cache hit  __main__:enrich [680674f58f]
recipe-cache miss __main__:enrich [8ef21130d8]: input events changed (/nfs/events.parquet); computed in 1.51s
```

`python -m recipe_cache ROOT` lists stored results. `python -m recipe_cache ROOT gc --keep N`
keeps the N most recently used results of each function.

## Key parts

| Part | Identity | Changes that force recomputation |
|---|---|---|
| Function | Bytecode, defaults, closure values, constant globals it names | Logic or constant edits. Comments, docstrings, and moved lines do not count. |
| Helpers | Every project function that ran during the computation, identified the same way | Edits to any helper that ran. Edits to helpers that did not run do not count. |
| Arguments | JSON-like values, dataclasses, enums, dates | Any value change. |
| `File` inputs | Absolute path plus size and modification time of each file; `identity="content"` hashes bytes | In-place overwrites that update metadata. |
| Upstream results | Digest of the stored bytes | Only a changed upstream value. An upstream recomputation with identical bytes reuses downstream results. |
| Environment | Python version and all installed distribution versions | Any package change. |

Helpers are found by `sys.monitoring` while the function runs. This includes
functions defined in notebook cells and Python functions that Polars calls from
its own threads. Library and standard-library code is covered by the environment.

## Rules for persisted functions

- Read data only through `File` arguments or upstream results. A string that names
  an existing absolute path gives a warning.
- Do not call a persisted function from another one. Call both at the top level and
  pass the result. This keeps every dependency visible in the key.
- Keep inputs to slow steps small: pass only the configuration values the step uses.
  Extra values cause unnecessary recomputation.
- Persist a step when it is slow and its output is reused. A persisted result stops
  lazy optimization such as filter pushdown across that boundary.

## Limits

- Undeclared reads are not detected. This includes files opened by Polars or DuckDB
  from a hard-coded path, databases, and network data. `audit` detects the
  resulting stale result by recomputation.
- Globals that have no identity, such as a module-level DataFrame, are not in
  the key. The store gives a warning and records them in the manifest as `unkeyed`.
- A helper that cannot be found again by module and name, for example through a
  decorator without `functools.wraps`, makes its caller recompute every time, with
  a warning.
- `stat` identity trusts NFS metadata. Attribute caching on other hosts can delay
  a changed modification time. `touch` without a content change forces recomputation;
  use `identity="content"` where that matters.
- `audit` and early cutoff compare bytes. A function with nondeterministic row
  order (for example `group_by` without `maintain_order`) reports a mismatch.
- Locks use `flock`. Cross-host locking on NFS depends on the mount.
- Pickled values load only while their classes stay importable.

## Tests

`uv run pytest tests` runs the end-to-end tests. `tests/test_e2e.py` runs a small
Polars pipeline whose module is rewritten and reloaded. `tests/test_notebook.py`
runs `example.py` as a Jupytext notebook in fresh kernels. Each test names the
failure it detects.
