"""Identity of the parts of a computation: code, arguments, files, environment.

Every identity here is a pure function of state visible to this process. No
identity uses Python's randomized ``hash()``, so keys agree across processes.
"""
from __future__ import annotations

import dataclasses
import datetime
import enum
import functools
import hashlib
import importlib
import importlib.metadata
import inspect
import json
import os
import platform
import sys
import types
from typing import Any, Callable, Literal

PROTOCOL = 1


def digest(state: Any) -> str:
    text = json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.blake2b(text.encode(), digest_size=16).hexdigest()


def file_digest(path: str) -> str:
    hasher = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as stream:
        while chunk := stream.read(1 << 22):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclasses.dataclass(frozen=True)
class File:
    """A data input addressed by path. A directory covers every file below it.

    ``stat`` identity uses size and modification time; it detects in-place
    overwrites that update metadata. ``content`` identity reads every byte.
    """

    path: str
    identity: Literal["stat", "content"] = "stat"

    def __post_init__(self):
        object.__setattr__(self, "path", os.path.abspath(os.fspath(self.path)))
        if self.identity not in ("stat", "content"):
            raise ValueError(f"unknown file identity {self.identity!r}")

    def fingerprint(self) -> list:
        if os.path.isdir(self.path):
            members = sorted(os.path.join(folder, name)
                             for folder, _, names in os.walk(self.path) for name in names)
        else:
            members = [self.path]
        return [[os.path.relpath(member, self.path), self._member(member)] for member in members]

    def _member(self, path: str):
        if self.identity == "content":
            return file_digest(path)
        status = os.stat(path)
        return [status.st_size, status.st_mtime_ns]


class Unidentified(TypeError):
    """An argument has no identity this store can compute."""


def canonical(value: Any, reference: Callable[[Any], Any] | None = None) -> Any:
    """Return a JSON state that identifies ``value``, or raise ``Unidentified``.

    ``reference`` identifies values the store produced; it returns None for others.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return {"float": repr(value)}
    if isinstance(value, File):
        return {"file": value.path, "identity": value.identity, "fingerprint": value.fingerprint()}
    if isinstance(value, enum.Enum):
        return {"enum": f"{type(value).__module__}.{type(value).__qualname__}.{value.name}"}
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)):
        return {type(value).__name__: str(value)}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, (list, tuple)):
        return [canonical(item, reference) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [canonical(item, reference) for item in value]
        return {"set": sorted(items, key=lambda item: json.dumps(item, sort_keys=True))}
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise Unidentified("dictionary keys must be strings")
        return {key: canonical(item, reference) for key, item in value.items()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = {field.name: canonical(getattr(value, field.name), reference)
                  for field in dataclasses.fields(value)}
        return {"dataclass": f"{type(value).__module__}.{type(value).__qualname__}", "fields": fields}
    if isinstance(value, os.PathLike):
        raise Unidentified(f"{value!r}: wrap data paths in File(...), or pass str for a label")
    if reference is not None and (state := reference(value)) is not None:
        return state
    raise Unidentified(f"cannot identify a {type(value).__module__}.{type(value).__qualname__} value")


# Code identity -------------------------------------------------------------

def _constant(value: Any) -> Any:
    if isinstance(value, types.CodeType):
        return _code(value)
    if isinstance(value, float):
        return {"float": repr(value)}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, tuple):
        return [_constant(item) for item in value]
    if isinstance(value, frozenset):
        return {"set": sorted(repr(item) for item in value)}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    return {"repr": repr(value)}


def _code(code: types.CodeType, docstring: bool = False) -> list:
    """Executed behaviour only: file names, line numbers, and docstrings are excluded."""
    constants = list(code.co_consts)
    if docstring and constants and isinstance(constants[0], str):
        constants[0] = None
    return [code.co_name, code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount,
            code.co_flags, code.co_code.hex(), code.co_exceptiontable.hex(), list(code.co_names),
            list(code.co_varnames), list(code.co_freevars), list(code.co_cellvars),
            [_constant(item) for item in constants]]


def _names(code: types.CodeType) -> set[str]:
    names = set(code.co_names)
    for item in code.co_consts:
        if isinstance(item, types.CodeType):
            names |= _names(item)
    return names


def function_state(function: Callable, depth: int = 0) -> tuple[list, list[str]]:
    """Identify a live function: bytecode, defaults, closure, and constant globals.

    Globals that are modules, classes, or module-level functions are skipped:
    executed project functions are identified through tracing, library code
    through the environment. Functions made by a factory carry their closure
    values, so they are identified here. Other globals without an identity are
    returned as ``unkeyed`` names.
    """
    function = inspect.unwrap(function)
    code = function.__code__
    unkeyed = []

    def value_state(name, value):
        if isinstance(value, functools.partial):
            return {"partial": value_state(name, value.func),
                    "args": [value_state(name, item) for item in value.args],
                    "keywords": {key: value_state(name, item) for key, item in value.keywords.items()}}
        if isinstance(value, types.FunctionType) and "<locals>" in value.__qualname__:
            if depth > 4:
                unkeyed.append(name)
                return None
            state, inner = function_state(value, depth + 1)
            unkeyed.extend(inner)
            return {"local function": digest(state)}
        if isinstance(value, (types.ModuleType, type)) or callable(value):
            return None
        try:
            return canonical(value)
        except Unidentified:
            unkeyed.append(name)
            return None

    namespace = function.__globals__
    constants = {name: state for name in sorted(_names(code)) if name in namespace
                 and (state := value_state(name, namespace[name])) is not None}
    closure = {}
    for name, cell in zip(code.co_freevars, function.__closure__ or ()):
        try:
            content = cell.cell_contents
        except ValueError:
            continue
        if isinstance(content, types.FunctionType) and "<locals>" not in content.__qualname__:
            closure[name] = function_id(content)
        elif (state := value_state(name, content)) is not None:
            closure[name] = state
    defaults = [value_state("<default>", value) for value in function.__defaults__ or ()]
    keyword_defaults = {name: value_state(name, value)
                        for name, value in (function.__kwdefaults__ or {}).items()}
    state = [_code(code, docstring=True), defaults, keyword_defaults, constants, closure]
    return state, unkeyed


def function_id(function: Callable) -> str:
    function = inspect.unwrap(function)
    return f"{function.__module__}:{function.__qualname__}"


def resolve(helper: str) -> Callable | None:
    """Find the live function a helper id names, or None."""
    module_name, qualname = helper.split(":", 1)
    try:
        target: Any = sys.modules.get(module_name) or importlib.import_module(module_name)
        for part in qualname.split("."):
            target = getattr(target, part)
    except (ImportError, AttributeError):
        return None
    target = inspect.unwrap(getattr(target, "__func__", target))
    return target if isinstance(target, types.FunctionType) else None


def helper_digest(helper: str) -> str | None:
    function = resolve(helper)
    return None if function is None else digest(function_state(function)[0])


# Environment identity ------------------------------------------------------

@functools.cache
def environment() -> dict:
    """Coarse: any installed distribution change invalidates every key."""
    distributions = sorted({f"{dist.metadata['Name']}=={dist.version}"
                            for dist in importlib.metadata.distributions()})
    return {"protocol": PROTOCOL, "python": sys.version, "implementation": platform.python_implementation(),
            "distributions": digest(distributions)}
