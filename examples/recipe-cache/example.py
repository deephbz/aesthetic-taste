# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
# ---

# %% [markdown]
# # Recipe cache example
#
# One slow step is persisted explicitly. Presentation stays cheap and is
# recomputed on every run. Restart the kernel and run all: the slow step is
# reused until its code, a helper it runs, its arguments, or its input file changes.

# %%
import os
import time
from pathlib import Path

import numpy as np
import polars as pl
from recipe_cache import File, Store

ROOT = Path(os.environ.get("RECIPE_CACHE_EXAMPLE", ".recipe-cache-example"))
store = Store(ROOT / "store")
source = ROOT / "events.parquet"
if not source.exists():
    generator = np.random.default_rng(7)
    pl.DataFrame({
        "sym": generator.choice(["ES", "NQ", "RTY"], 100_000),
        "px": generator.normal(100, 5, 100_000),
        "qty": generator.integers(1, 10, 100_000),
    }).write_parquet(source)
EVENTS = File(source)

# %%
def notional(frame):
    return frame.with_columns((pl.col("px") * pl.col("qty")).alias("notional"))


# %%
@store.persist
def enrich(events: File, window: int):
    time.sleep(1.5)  # Stands in for a slow join.
    frame = notional(pl.read_parquet(events.path))
    return frame.with_columns(pl.col("notional").rolling_mean(window).over("sym").alias("smooth"))


enriched = enrich(EVENTS, window=5)

# %%
enriched.group_by("sym").agg(pl.col("smooth").mean()).sort("sym")
