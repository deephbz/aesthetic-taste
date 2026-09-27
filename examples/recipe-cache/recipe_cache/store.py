"""Explicitly persisted computations with keys derived from what they depend on.

A result is reused only when its function code, arguments, input files,
environment, and every project helper that ran while computing it are unchanged.
Persistence is opt-in per function; nothing else is cached.
"""
from __future__ import annotations

import contextvars
import dataclasses
import fcntl
import inspect
import json
import os
import shutil
import sys
import time
import uuid
import warnings
import weakref
from contextlib import contextmanager
from typing import Any, Callable, Literal

from . import codecs, tracing
from .identity import (Unidentified, canonical, digest, environment, file_digest,
                       function_id, function_state, helper_digest, resolve)

UNRESOLVED = "unresolved"
_running: contextvars.ContextVar[str | None] = contextvars.ContextVar("recipe_cache_running", default=None)
_results: dict[int, tuple[weakref.ref, dict]] = {}


def _tag(value: Any, state: dict) -> None:
    """Remember which stored result a returned object is, so it can be passed on."""
    key = id(value)
    try:
        _results[key] = (weakref.ref(value, lambda _: _results.pop(key, None)), state)
    except TypeError:
        pass  # Plain values such as int are identified by canonical() instead.


def _reference(value: Any) -> dict | None:
    item = _results.get(id(value))
    return item[1] if item is not None and item[0]() is value else None


class NestedCall(RuntimeError):
    """A persisted function called another persisted function."""


@dataclasses.dataclass(frozen=True)
class Decision:
    function: str
    status: Literal["hit", "miss"]
    entry: str | None
    reasons: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Audit:
    function: str
    entry: str
    stored: str
    fresh: str

    @property
    def match(self) -> bool:
        return self.stored == self.fresh


@dataclasses.dataclass
class _Call:
    function: str
    parts: dict
    static_key: str
    unkeyed: list[str]


class Store:
    """A directory of persisted results. Share it between kernels and scripts.

    Layout: ``entries/<key>/`` holds the value file and ``manifest.json``;
    ``index/<static key>.json`` lists entries with their helper digests;
    ``functions/`` points at each function's latest result for explanations.
    """

    def __init__(self, root: str | os.PathLike, *, quiet: bool = False):
        self.root = os.path.abspath(os.fspath(root))
        self.quiet = quiet
        for folder in ("entries", "index", "functions", "locks", "tmp"):
            os.makedirs(os.path.join(self.root, folder), exist_ok=True)

    def persist(self, function: Callable | None = None, *, name: str | None = None):
        """Decorate or wrap a function whose results this store keeps."""
        if function is None:
            return lambda body: Persisted(self, body, name)
        return Persisted(self, function, name)

    # Storage ---------------------------------------------------------------

    def _path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def _read(self, *parts: str) -> Any:
        try:
            with open(self._path(*parts)) as stream:
                return json.load(stream)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _write(self, data: Any, *parts: str) -> None:
        target = self._path(*parts)
        temporary = self._path("tmp", uuid.uuid4().hex)
        with open(temporary, "w") as stream:
            json.dump(data, stream, indent=1, sort_keys=True)
        os.replace(temporary, target)

    def manifest(self, entry: str) -> dict | None:
        """Return a stored entry's manifest when its value file is also present."""
        manifest = self._read("entries", entry, "manifest.json")
        if manifest is None or not os.path.exists(self._path("entries", entry, manifest["value"])):
            return None
        return manifest

    def entries(self) -> list[dict]:
        found = (self.manifest(entry) for entry in os.listdir(self._path("entries")))
        return sorted((item for item in found if item), key=lambda item: item["created"])

    @contextmanager
    def _lock(self, static_key: str):
        with open(self._path("locks", static_key + ".lock"), "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _lookup(self, call: _Call) -> dict | None:
        for candidate in reversed(self._read("index", call.static_key + ".json") or []):
            if all(helper_digest(helper) == value for helper, value in candidate["helpers"].items()):
                if (manifest := self.manifest(candidate["entry"])) is not None:
                    return manifest
        return None

    def _publish(self, call: _Call, value: Any, helpers: dict, unkeyed: list, elapsed: float) -> dict:
        entry = digest([call.static_key, helpers])
        codec = codecs.for_value(value)
        staging = self._path("tmp", uuid.uuid4().hex)
        os.makedirs(staging)
        try:
            value_file = "value" + codec.suffix
            codec.save(value, os.path.join(staging, value_file))
            path = os.path.join(staging, value_file)
            manifest = {
                "entry": entry, "function": call.function, "static_key": call.static_key,
                "parts": call.parts, "helpers": helpers, "unkeyed": unkeyed,
                "codec": codec.name, "value": value_file, "bytes": os.path.getsize(path),
                "digest": file_digest(path), "description": codec.describe(path),
                "elapsed_s": round(elapsed, 6), "created": time.time(),
            }
            with open(os.path.join(staging, "manifest.json"), "w") as stream:
                json.dump(manifest, stream, indent=1, sort_keys=True)
            destination = self._path("entries", entry)
            shutil.rmtree(destination, ignore_errors=True)
            os.rename(staging, destination)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        index = [item for item in self._read("index", call.static_key + ".json") or []
                 if item["entry"] != entry]
        self._write(index[-7:] + [{"entry": entry, "helpers": helpers}], "index", call.static_key + ".json")
        return manifest

    def _load(self, manifest: dict) -> Any:
        entry_path = self._path("entries", manifest["entry"])
        os.utime(entry_path)  # Last use, for garbage collection.
        self._write({"entry": manifest["entry"]}, "functions", _safe(manifest["function"]) + ".json")
        value = codecs.named(manifest["codec"]).load(os.path.join(entry_path, manifest["value"]))
        _tag(value, {"result": manifest["digest"]})
        return value

    def gc(self, keep: int = 1) -> list[str]:
        """Delete all but each function's ``keep`` most recently used results."""
        removed = []
        by_function: dict[str, list[str]] = {}
        for manifest in self.entries():
            by_function.setdefault(manifest["function"], []).append(manifest["entry"])
        for entries in by_function.values():
            entries.sort(key=lambda entry: os.path.getmtime(self._path("entries", entry)), reverse=True)
            for entry in entries[keep:]:
                shutil.rmtree(self._path("entries", entry), ignore_errors=True)
                removed.append(entry)
        horizon = time.time() - 3600
        for name in os.listdir(self._path("tmp")):
            path = self._path("tmp", name)
            if os.path.getmtime(path) < horizon:
                shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)
        return removed

    # Explanation -------------------------------------------------------------

    def _reasons(self, call: _Call) -> tuple[str, ...]:
        candidates = self._read("index", call.static_key + ".json") or []
        if candidates:
            latest = candidates[-1]
            changed = tuple(f"helper {helper} changed" for helper, value in latest["helpers"].items()
                            if helper_digest(helper) != value)
            return changed or ("stored result missing",)
        pointer = self._read("functions", _safe(call.function) + ".json")
        previous = pointer and self._read("entries", pointer["entry"], "manifest.json")
        if not previous:
            return ("no stored result",)
        before, now = previous["parts"], call.parts
        reasons = []
        if before["code"] != now["code"]:
            reasons.append(f"code of {call.function} changed")
        for name in sorted(set(before["arguments"]) | set(now["arguments"])):
            old, new = before["arguments"].get(name), now["arguments"].get(name)
            if old != new:
                reasons.append(_argument_change(name, old, new))
        if before["environment"] != now["environment"]:
            reasons.append("environment changed")
        reasons += [f"helper {helper} changed" for helper, value in previous["helpers"].items()
                    if helper_digest(helper) != value]
        return tuple(reasons) or ("key changed",)

    def _report(self, decision: Decision, elapsed: float | None = None) -> None:
        if self.quiet:
            return
        entry = decision.entry[:10] if decision.entry else "-"
        details = list(decision.reasons)
        if elapsed is not None:
            details.append(f"computed in {elapsed:.2f}s")
        suffix = ": " + "; ".join(details) if details else ""
        print(f"recipe-cache {decision.status} {decision.function} [{entry}]{suffix}", file=sys.stderr)


def _argument_change(name: str, old: Any, new: Any) -> str:
    if isinstance(new, dict) and "file" in new:
        return f"input {name} changed ({new['file']})"
    if isinstance(new, dict) and "result" in new:
        return f"upstream result {name} changed"
    return f"argument {name} changed"


def _safe(function: str) -> str:
    return function.replace(":", "__").replace("<", "_").replace(">", "_")


class Persisted:
    """A function whose results a Store keeps. Call it like the function itself.

    Arguments must be identifiable: JSON-like values, dataclasses, enums, dates,
    ``File`` inputs, or values returned by other persisted calls. A persisted
    function must not call another persisted function; pass results as arguments.
    """

    def __init__(self, store: Store, function: Callable, name: str | None):
        self.store = store
        self.function = function
        self.name = name or function_id(function)
        self.signature = inspect.signature(function)
        self.__wrapped__ = function
        self.__doc__ = function.__doc__

    def _call(self, args, kwargs) -> _Call:
        bound = self.signature.bind(*args, **kwargs)
        bound.apply_defaults()
        arguments = {}
        for name, value in bound.arguments.items():
            try:
                arguments[name] = canonical(value, _reference)
            except Unidentified as error:
                raise Unidentified(f"{self.name} argument {name!r}: {error}. Pass a File, a value "
                                   "returned by a persisted call, or a JSON-like value.") from None
            if isinstance(value, str) and os.path.isabs(value) and os.path.exists(value):
                warnings.warn(f"{self.name} argument {name!r} looks like a data path; pass File(...) "
                              "so that changes to the file invalidate the result", stacklevel=4)
        state, unkeyed = function_state(self.function)
        parts = {"function": self.name, "code": digest(state), "arguments": arguments,
                 "environment": environment()}
        return _Call(self.name, parts, digest(parts), unkeyed)

    def explain(self, *args, **kwargs) -> Decision:
        """Say whether a call would reuse a stored result, without computing."""
        call = self._call(args, kwargs)
        manifest = self.store._lookup(call)
        if manifest is not None:
            return Decision(self.name, "hit", manifest["entry"])
        return Decision(self.name, "miss", None, self.store._reasons(call))

    def __call__(self, *args, **kwargs):
        return self._run(args, kwargs, reuse=True)

    def refresh(self, *args, **kwargs):
        """Recompute and replace the stored result."""
        return self._run(args, kwargs, reuse=False)

    def _run(self, args, kwargs, reuse: bool):
        self._guard()
        call = self._call(args, kwargs)
        with self.store._lock(call.static_key):
            manifest = self.store._lookup(call) if reuse else None
            if manifest is not None:
                self.store._report(Decision(self.name, "hit", manifest["entry"]))
                return self.store._load(manifest)
            reasons = self.store._reasons(call) if reuse else ("refresh requested",)
            value, helpers, unkeyed, elapsed = self._compute(call, args, kwargs)
            manifest = self.store._publish(call, value, helpers, unkeyed, elapsed)
        self.store._report(Decision(self.name, "miss", manifest["entry"], reasons), elapsed)
        return self.store._load(manifest)

    def audit(self, *args, **kwargs) -> Audit:
        """Recompute a stored result and compare bytes. Detects missing key parts.

        A mismatch means the function read something its key does not cover, or
        is not deterministic. The stored result is left unchanged.
        """
        self._guard()
        call = self._call(args, kwargs)
        manifest = self.store._lookup(call)
        if manifest is None:
            raise LookupError(f"{self.name}: no stored result to audit")
        token = _running.set(self.name)
        try:
            value = self.function(*args, **kwargs)
        finally:
            _running.reset(token)
        codec = codecs.for_value(value)
        staging = self.store._path("tmp", uuid.uuid4().hex + codec.suffix)
        try:
            codec.save(value, staging)
            audit = Audit(self.name, manifest["entry"], manifest["digest"], file_digest(staging))
        finally:
            if os.path.exists(staging):
                os.remove(staging)
        if not audit.match and not self.store.quiet:
            print(f"recipe-cache AUDIT MISMATCH {self.name} [{audit.entry[:10]}]: the stored result "
                  "differs from a fresh computation", file=sys.stderr)
        return audit

    def _guard(self):
        if (outer := _running.get()) is not None:
            raise NestedCall(f"{outer} called persisted {self.name}; call it outside and pass its "
                             "result as an argument")

    def _compute(self, call: _Call, args, kwargs):
        top = inspect.unwrap(self.function).__code__
        token = _running.set(self.name)
        codes = tracing.start()
        started = time.perf_counter()
        try:
            value = self.function(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - started
            tracing.stop(codes)
            _running.reset(token)
        helpers, unkeyed = {}, list(call.unkeyed)
        for code in codes:
            # Nested functions, lambdas, and comprehensions are part of their enclosing code.
            if code is top or "<" in code.co_qualname:
                continue
            helper = f"{tracing.module_of(code)}:{code.co_qualname}"
            function = resolve(helper)
            if function is None or function.__code__ is not code:
                helpers[helper] = UNRESOLVED
                continue
            state, inner = function_state(function)
            helpers[helper] = digest(state)
            unkeyed += [f"{helper}.{name}" for name in inner]
        unresolved = sorted(helper for helper, value in helpers.items() if value == UNRESOLVED)
        if unresolved:
            warnings.warn(f"{self.name}: cannot identify helpers {unresolved}; "
                          "this result will not be reused", stacklevel=4)
        if unkeyed:
            warnings.warn(f"{self.name}: globals without identity are not in the key: "
                          f"{sorted(set(unkeyed))}", stacklevel=4)
        return value, helpers, sorted(set(unkeyed)), elapsed
