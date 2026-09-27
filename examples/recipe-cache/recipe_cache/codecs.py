"""Write and read persisted values. The first codec that accepts a value owns it.

A persisted call always returns the value read back from storage, so a caller
sees the same result on a first computation and on a later reuse.
"""
from __future__ import annotations

import pickle
import sys
from typing import Any, Protocol


class Codec(Protocol):
    name: str
    suffix: str

    def accepts(self, value: Any) -> bool: ...
    def save(self, value: Any, path: str) -> None: ...
    def load(self, path: str) -> Any: ...
    def describe(self, path: str) -> dict: ...


def _polars():
    return sys.modules.get("polars")


class PolarsFrame:
    name, suffix = "polars.DataFrame", ".parquet"

    def accepts(self, value):
        return (pl := _polars()) is not None and isinstance(value, pl.DataFrame)

    def save(self, value, path):
        value.write_parquet(path)

    def load(self, path):
        return _polars().read_parquet(path)

    def describe(self, path):
        pl = _polars()
        return {"rows": pl.scan_parquet(path).select(pl.len()).collect().item(),
                "schema": {name: str(dtype) for name, dtype in pl.read_parquet_schema(path).items()}}


class PolarsLazy(PolarsFrame):
    """Streams the plan to Parquet; reuse returns a lazy scan of the stored file."""

    name = "polars.LazyFrame"

    def accepts(self, value):
        return (pl := _polars()) is not None and isinstance(value, pl.LazyFrame)

    def save(self, value, path):
        value.sink_parquet(path)

    def load(self, path):
        return _polars().scan_parquet(path)


class Pickle:
    name, suffix = "pickle", ".pickle"

    def accepts(self, value):
        return True

    def save(self, value, path):
        with open(path, "wb") as stream:
            pickle.dump(value, stream, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, path):
        with open(path, "rb") as stream:
            return pickle.load(stream)

    def describe(self, path):
        return {}


CODECS: list[Codec] = [PolarsFrame(), PolarsLazy(), Pickle()]


def register(codec: Codec) -> None:
    """Add a codec ahead of the built-in ones, for example a DuckDB relation codec."""
    CODECS.insert(0, codec)


def for_value(value: Any) -> Codec:
    return next(codec for codec in CODECS if codec.accepts(value))


def named(name: str) -> Codec:
    return next(codec for codec in CODECS if codec.name == name)
