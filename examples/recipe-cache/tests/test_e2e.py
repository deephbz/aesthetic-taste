"""End-to-end behaviour of persisted computations on a small Polars pipeline.

Each test names the failure it detects. The pipeline module is written to disk
and reloaded, so helper edits reach the process the way they do in real work.
"""
import importlib
import os
import subprocess
import sys
import textwrap

import polars as pl
import pytest

from recipe_cache import File, NestedCall, Store, Unidentified

PIPELINE = '''
import polars as pl

SCALE = {scale}


def clean(frame):
    {clean}


def unused():
    return {unused}


def join(events, prices, tolerance: int = 0):
    frame = pl.read_parquet(events.path).join(pl.read_parquet(prices.path), on="id")
    return clean(frame.filter(pl.col("qty") > tolerance)){join_suffix}


def summarize(joined, by: str = "sym"):
    return joined.group_by(by).agg((pl.col("px") * pl.col("qty")).sum() * SCALE).sort(by)


def lazy_total(events):
    return pl.scan_parquet(events.path).select(pl.col("qty").sum())
'''
DEFAULTS = dict(scale=1, clean="return frame.drop_nulls()", unused=0, join_suffix="")


@pytest.fixture
def world(tmp_path, monkeypatch):
    data = tmp_path / "nfs"
    data.mkdir()
    pl.DataFrame({"id": [1, 2, 3, 4], "sym": ["a", "b", "a", "b"], "qty": [1, 2, 3, 4]}).write_parquet(data / "events.parquet")
    pl.DataFrame({"id": [1, 2, 3, 4], "px": [10.0, 20.0, 30.0, None]}).write_parquet(data / "prices.parquet")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("pipeline", None)

    class World:
        root = tmp_path
        events = File(data / "events.parquet")
        prices = File(data / "prices.parquet")
        store = Store(tmp_path / "store")

        def module(self, **changes):
            source = PIPELINE.format(**{**DEFAULTS, **changes})
            (tmp_path / "pipeline.py").write_text(source)
            importlib.invalidate_caches()
            module = importlib.reload(sys.modules["pipeline"]) if "pipeline" in sys.modules else importlib.import_module("pipeline")
            self.join = self.store.persist(module.join)
            self.summarize = self.store.persist(module.summarize)
            self.lazy_total = self.store.persist(module.lazy_total)
            return module

    world = World()
    world.module()
    yield world
    sys.modules.pop("pipeline", None)


def outcomes(capsys):
    """(status, reasons) per persisted call, parsed from the one-line reports."""
    lines = [line for line in capsys.readouterr().err.splitlines() if line.startswith("recipe-cache")]
    return [(line.split()[1], line.split("]", 1)[1]) for line in lines]


def test_reuse_returns_the_same_value_without_recomputing(world, capsys):
    """Detects: a reused result that differs from the computed one, or a lost value type."""
    first = world.join(world.events, world.prices)
    second = world.join(world.events, world.prices)
    assert [status for status, _ in outcomes(capsys)] == ["miss", "hit"]
    assert first.equals(second) and first.height == 3
    assert isinstance(world.lazy_total(world.events), pl.LazyFrame)
    assert world.lazy_total(world.events).collect().item() == 10


def test_argument_change_recomputes_and_old_result_stays_available(world, capsys):
    """Detects: parameters missing from the key."""
    world.join(world.events, world.prices, tolerance=0)
    world.join(world.events, world.prices, tolerance=2)
    world.join(world.events, world.prices, tolerance=0)
    result = outcomes(capsys)
    assert [status for status, _ in result] == ["miss", "miss", "hit"]
    assert "argument tolerance changed" in result[1][1]


def test_in_place_overwrite_of_an_input_recomputes(world, capsys):
    """Detects: an input identified by its path only."""
    world.join(world.events, world.prices)
    path = world.prices.path
    before = os.stat(path).st_mtime_ns
    pl.DataFrame({"id": [1, 2, 3, 4], "px": [11.0, 20.0, 30.0, None]}).write_parquet(path)
    os.utime(path, ns=(before + 10**9, before + 10**9))
    world.join(world.events, world.prices)
    result = outcomes(capsys)
    assert result[1][0] == "miss" and f"input prices changed ({path})" in result[1][1]


def test_helper_edits_recompute_and_cosmetic_edits_do_not(world, capsys):
    """Detects: helper code missing from the key, and spurious recomputation."""
    world.join(world.events, world.prices)
    world.module(clean='"""Drop incomplete rows."""\n    # Explain nothing.\n\n    return frame.drop_nulls()')
    world.join(world.events, world.prices)
    world.module(unused=1)
    world.join(world.events, world.prices)
    world.module(clean="return frame.fill_null(0.0)")
    changed = world.join(world.events, world.prices)
    result = outcomes(capsys)
    assert [status for status, _ in result] == ["miss", "hit", "hit", "miss"]
    assert "helper pipeline:clean changed" in result[3][1]
    assert changed.height == 4


def test_global_constant_change_recomputes(world, capsys):
    """Detects: module constants read by a function missing from the key."""
    joined = world.join(world.events, world.prices)
    world.summarize(joined)
    world.module(scale=100)
    scaled = world.summarize(world.join(world.events, world.prices))
    result = outcomes(capsys)
    assert [status for status, _ in result] == ["miss", "miss", "hit", "miss"]
    assert "code of pipeline:summarize changed" in result[3][1]
    assert scaled["px"].to_list() == [10000.0, 4000.0]


def test_equivalent_upstream_result_reuses_downstream(world, capsys):
    """Detects: downstream recomputation when an upstream change leaves its bytes unchanged."""
    world.summarize(world.join(world.events, world.prices))
    world.module(join_suffix=".select(pl.all())")
    world.summarize(world.join(world.events, world.prices))
    world.module(join_suffix=".filter(pl.col('sym') == 'a')")
    world.summarize(world.join(world.events, world.prices))
    result = outcomes(capsys)
    assert [status for status, _ in result] == ["miss", "miss", "miss", "hit", "miss", "miss"]
    assert "upstream result joined changed" in result[5][1]


def test_failed_or_damaged_results_are_never_reused(world, capsys):
    """Detects: partial publication, and reuse of a result whose value file is gone."""
    def broken(events: File):
        raise RuntimeError("interrupted")
    with pytest.raises(RuntimeError):
        world.store.persist(broken)(world.events)
    assert world.store.entries() == []
    world.join(world.events, world.prices)
    [manifest] = world.store.entries()
    os.remove(world.root / "store" / "entries" / manifest["entry"] / manifest["value"])
    world.join(world.events, world.prices)
    result = outcomes(capsys)
    assert result[1][0] == "miss" and "stored result missing" in result[1][1]


def test_arguments_without_identity_are_rejected(world):
    """Detects: silent keys for data whose origin the store cannot identify."""
    with pytest.raises(Unidentified, match="joined"):
        world.summarize(pl.DataFrame({"sym": ["a"], "px": [1.0], "qty": [1]}))


def test_nested_persisted_calls_are_rejected(world):
    """Detects: hidden edges that would leave the outer key without its inputs."""
    inner = world.join

    def outer(events: File, prices: File):
        return inner(events, prices)
    with pytest.raises(NestedCall):
        world.store.persist(outer)(world.events, world.prices)


def test_new_process_reuses_the_result(world, capsys):
    """Detects: keys that depend on process state such as hash randomization."""
    world.join(world.events, world.prices)
    script = textwrap.dedent(f"""
        import sys; sys.path.insert(0, {str(world.root)!r})
        import pipeline
        from recipe_cache import File, Store
        store = Store({str(world.root / 'store')!r})
        store.persist(pipeline.join)(File({world.events.path!r}), File({world.prices.path!r}))
    """)
    run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                         env={**os.environ, "PYTHONHASHSEED": "7"})
    assert run.returncode == 0, run.stderr
    assert "recipe-cache hit pipeline:join" in run.stderr


def test_audit_detects_an_undeclared_input(world, tmp_path, capsys):
    """Detects: a function that reads a file its key does not cover."""
    side = tmp_path / "side.txt"
    side.write_text("1")

    def undeclared(label: str):
        return pl.DataFrame({"value": [int(open(label).read())]})
    persisted = world.store.persist(undeclared)
    with pytest.warns(UserWarning, match="looks like a data path"):
        persisted(str(side))
        side.write_text("2")
        stale = persisted(str(side))
        audit = persisted.audit(str(side))
    assert stale["value"].item() == 1
    assert not audit.match


LOOKUP = pl.DataFrame({"sym": ["a", "b"], "weight": [1.0, 2.0]})


def weighted(joined):
    return joined.join(LOOKUP, on="sym")


def test_globals_without_identity_are_reported(world):
    """Detects: a silent key that omits a module-level table the function reads."""
    joined = world.join(world.events, world.prices)
    with pytest.warns(UserWarning, match=r"globals without identity .*LOOKUP"):
        world.store.persist(weighted)(joined)
    [manifest] = [item for item in world.store.entries() if item["function"].endswith("weighted")]
    assert manifest["unkeyed"] == ["LOOKUP"]
