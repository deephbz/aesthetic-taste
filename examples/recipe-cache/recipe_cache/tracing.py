"""Record which project functions run during a computation.

Library and standard-library code is excluded; the environment identity covers
it. Each code object reports once per trace and then disables its own event,
so steady-state overhead is near zero. Events are process-wide: calls from
engine threads (for example Polars user-defined functions) are recorded too.
"""
from __future__ import annotations

import os
import site
import sys
import sysconfig
import types
from functools import cache

_monitoring = sys.monitoring
_PACKAGE = os.path.dirname(os.path.abspath(__file__)) + os.sep
_active: list[set[types.CodeType]] = []
_tool: int | None = None


@cache
def _library_roots() -> tuple[str, ...]:
    paths = sysconfig.get_paths()
    roots = {paths[key] for key in ("stdlib", "platstdlib", "purelib", "platlib")}
    roots.update(site.getsitepackages())
    return tuple(os.path.abspath(root) + os.sep for root in roots)


@cache
def tracked(filename: str) -> bool:
    if filename.startswith("<"):
        return False
    path = os.path.abspath(filename)
    return not path.startswith(_PACKAGE) and not path.startswith(_library_roots())


def _on_start(code: types.CodeType, offset: int):
    if tracked(code.co_filename):
        for codes in _active:
            codes.add(code)
    return _monitoring.DISABLE


def start() -> set[types.CodeType]:
    global _tool
    if _tool is None:
        _tool = next(tool for tool in (3, 4, 2, 1, 0) if _monitoring.get_tool(tool) is None)
        _monitoring.use_tool_id(_tool, "recipe_cache")
        _monitoring.register_callback(_tool, _monitoring.events.PY_START, _on_start)
        _monitoring.set_events(_tool, _monitoring.events.PY_START)
    # Re-enable code objects disabled by an earlier or enclosing trace.
    _monitoring.restart_events()
    codes: set[types.CodeType] = set()
    _active.append(codes)
    return codes


def stop(codes: set[types.CodeType]) -> None:
    global _tool
    _active.remove(codes)
    if not _active and _tool is not None:
        _monitoring.set_events(_tool, 0)
        _monitoring.register_callback(_tool, _monitoring.events.PY_START, None)
        _monitoring.free_tool_id(_tool)
        _tool = None


_files: dict[str, str] = {}


def module_of(code: types.CodeType) -> str:
    """Map a code object to its defining module; notebook cells map to ``__main__``."""
    path = os.path.abspath(code.co_filename)
    if path not in _files:
        for name, module in list(sys.modules.items()):
            if file := getattr(module, "__file__", None):
                _files.setdefault(os.path.abspath(file), name)
    return _files.get(path, "__main__")
