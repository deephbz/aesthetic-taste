"""Live Jupyter notebook operations for agent-human collaboration.

Purpose: expose small, cell-aware operations against a running Jupyter
Server document and its kernel.
Scope: this module owns the CLI boundary for live notebook inspection,
editing, execution, scratch evaluation, and one-way export. It does not own
notebook trust policy, conflict resolution, or expensive computation caches.
The live document is authoritative while collaboration is active.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit


MAX_WEBSOCKET_BODY_SIZE = 128 * 1024 * 1024
DEFAULT_TIMEOUT = 30.0


class NotebookError(RuntimeError):
    """A user-actionable live-notebook operation failure."""


@dataclass(frozen=True)
class ServerConfig:
    """Credentials and origin for one Jupyter Server connection."""

    url: str
    token: str
    root_dir: Path | None = None


def read_server(path: str | Path) -> ServerConfig:
    """Read a Jupyter server JSON file without exposing its token."""

    location = Path(path).expanduser()
    try:
        data = json.loads(location.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise NotebookError(f"server credential file does not exist: {location}") from error
    except json.JSONDecodeError as error:
        raise NotebookError(f"server credential file is not valid JSON: {location}") from error
    if not isinstance(data, Mapping):
        raise NotebookError(f"server credential file must contain an object: {location}")
    url = data.get("url")
    token = data.get("token")
    if not isinstance(url, str) or not url.strip():
        raise NotebookError(f"server credential file has no usable url: {location}")
    if not isinstance(token, str):
        raise NotebookError(f"server credential file has no usable token: {location}")
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        raise NotebookError(f"server credential file has no usable url: {location}")
    if parts.username is not None or parts.password is not None:
        raise NotebookError("server url must not contain username or password credentials")
    base_url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    root_value = data.get("root_dir")
    root_dir = Path(root_value).expanduser().resolve() if isinstance(root_value, str) else None
    return ServerConfig(url=base_url, token=token, root_dir=root_dir)


def _optional_dependencies() -> tuple[Any, Any, Any, Callable[..., str]]:
    """Import live notebook dependencies only when a notebook command runs."""

    try:
        import requests
        from jupyter_kernel_client import JupyterKernelClient
        from jupyter_nbmodel_client import NbModelClient, get_notebook_websocket_url
    except ImportError as error:
        raise NotebookError(
            "live notebook commands need the notebook extra; run "
            "'uv run --project components/reporting --extra notebook report notebook ...'"
        ) from error
    return requests, JupyterKernelClient, NbModelClient, get_notebook_websocket_url


def _jupytext() -> Any:
    try:
        import jupytext
    except ImportError as error:
        raise NotebookError(
            "Python export needs the notebook extra; run "
            "'uv run --project components/reporting --extra notebook report notebook export ...'"
        ) from error
    return jupytext


def _native_notebook(snapshot: Mapping[str, Any]) -> Any:
    """Validate and materialize a JSON-ready snapshot as a NotebookNode."""

    try:
        import nbformat
    except ImportError as error:
        raise NotebookError(
            "notebook export needs nbformat; run "
            "'uv run --project components/reporting --extra notebook report notebook export ...'"
        ) from error
    try:
        node = nbformat.from_dict(dict(snapshot))
        for cell in node.cells:
            if not cell.get("id"):
                cell["id"] = uuid.uuid4().hex[:8]
        nbformat.validate(node)
    except Exception as error:
        raise NotebookError("live notebook snapshot failed nbformat validation") from error
    return node


def _headers(config: ServerConfig) -> dict[str, str]:
    return {"Authorization": f"token {config.token}"}


def _request(requests: Any, config: ServerConfig, method: str, path: str, **kwargs: Any) -> Any:
    """Make an authenticated server request and hide credentials in failures."""

    kwargs.setdefault("headers", _headers(config))
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    try:
        response = requests.request(method, f"{config.url}{path}", **kwargs)
        response.raise_for_status()
    except Exception as error:
        detail = getattr(error, "response", None)
        status = getattr(detail, "status_code", None)
        suffix = f" (HTTP {status})" if status else ""
        raise NotebookError(f"Jupyter Server request failed{suffix}: {method} {path}") from error
    return response


def session_for(
    config: ServerConfig,
    notebook: str,
    *,
    requests: Any | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any] | None:
    """Return the session for a notebook path, if one is running."""

    if requests is None:
        requests, _, _, _ = _optional_dependencies()
    response = _request(requests, config, "GET", "/api/sessions", timeout=timeout)
    for session in response.json():
        session_path = session.get("path") or session.get("notebook", {}).get("path")
        if session_path == notebook:
            return session
    return None


def _session_kernel_id(session: Mapping[str, Any] | None) -> str | None:
    if not session:
        return None
    kernel = session.get("kernel")
    return kernel.get("id") if isinstance(kernel, Mapping) else None


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def cell_index(model: Any, selector: str) -> int:
    """Resolve an integer index, native cell id, or collaboration stable name."""

    if selector.isdigit():
        index = int(selector)
        if 0 <= index < len(model):
            return index
    for index in range(len(model)):
        cell = model[index]
        metadata = _mapping(model.get_cell_metadata(index, "collaboration", {}))
        if metadata.get("stable_name") == selector or cell.get("id") == selector:
            return index
    raise NotebookError(f"cell selector not found: {selector}")


def _cell_execution_hash(metadata: Mapping[str, Any]) -> str | None:
    """Read an optional execution source hash emitted by a caller or adapter."""

    candidates: list[Any] = [
        metadata.get("executed_source_sha256"),
        metadata.get("execution_source_sha256"),
    ]
    for container_key in ("execution", "collaboration"):
        container = metadata.get(container_key)
        if isinstance(container, Mapping):
            candidates.extend(
                [container.get("executed_source_sha256"), container.get("source_sha256")]
            )
    return next((value for value in candidates if isinstance(value, str)), None)


def serialise_cell(model: Any, index: int) -> dict[str, Any]:
    """Return a JSON-ready cell view with source and execution provenance."""

    cell = model[index]
    source = model.get_cell_source(index)
    metadata = _mapping(model.get_cell_metadata(index, "collaboration", {}))
    source_hash = sha256_text(source)
    executed_hash = _cell_execution_hash(metadata)
    return {
        "index": index,
        "id": cell.get("id"),
        "cell_type": cell.get("cell_type"),
        "stable_name": metadata.get("stable_name"),
        "source": source,
        "source_sha256": source_hash,
        "executed_source_sha256": executed_hash,
        "source_executed_hash_mismatch": (
            None if executed_hash is None else executed_hash != source_hash
        ),
        "execution_count": cell.get("execution_count"),
        "outputs": cell.get("outputs", []),
    }


def _json_ready(value: Any) -> Any:
    """Convert NotebookNode-like values without leaking repr-only objects."""

    try:
        return json.loads(json.dumps(value, default=str))
    except TypeError:
        return str(value)


def notebook_snapshot(model: Any) -> dict[str, Any]:
    """Build a native nbformat snapshot from the live document model."""

    raw_cells = [_json_ready(dict(model[index])) for index in range(len(model))]
    cells: list[dict[str, Any]] = []
    for raw_cell in raw_cells:
        cell_type = raw_cell.get("cell_type", "code")
        # RTC adds transport-only fields such as execution_state. Keep the
        # native notebook schema as the export boundary.
        cell = {
            "cell_type": cell_type,
            "metadata": raw_cell.get("metadata", {}),
            "source": raw_cell.get("source", ""),
        }
        if raw_cell.get("id"):
            cell["id"] = raw_cell["id"]
        if cell_type == "code":
            cell["execution_count"] = raw_cell.get("execution_count")
            cell["outputs"] = raw_cell.get("outputs", [])
        elif "attachments" in raw_cell:
            cell["attachments"] = raw_cell["attachments"]
        cells.append(cell)
        execution_count = cell.get("execution_count")
        if isinstance(execution_count, float) and execution_count.is_integer():
            cell["execution_count"] = int(execution_count)
    metadata = _json_ready(getattr(model, "metadata", {}))
    return {
        "cells": cells,
        "metadata": metadata if isinstance(metadata, dict) else {},
        "nbformat": int(getattr(model, "nbformat", 4) or 4),
        "nbformat_minor": int(getattr(model, "nbformat_minor", 5) or 5),
    }


def _source_from_args(args: argparse.Namespace, *, required: bool = True) -> str:
    value = getattr(args, "source", None)
    source_file = getattr(args, "source_file", None)
    if value is not None and source_file is not None:
        raise NotebookError("choose one of --source and --source-file")
    if source_file is not None:
        if source_file == "-":
            return sys.stdin.read()
        location = Path(source_file).expanduser()
        try:
            return location.read_text(encoding="utf-8")
        except OSError as error:
            raise NotebookError(f"source file cannot be read: {location}") from error
    if value is None:
        if required:
            raise NotebookError("provide --source or --source-file")
        return ""
    return value


def _output_path(args: argparse.Namespace, config: ServerConfig | None = None) -> Path:
    raw = getattr(args, "output", None)
    if not raw:
        raise NotebookError("export requires an explicit --output path")
    output = Path(raw).expanduser()
    notebook = Path(args.notebook).expanduser()
    live_notebook = notebook
    if config is not None and config.root_dir is not None and not notebook.is_absolute():
        live_notebook = config.root_dir / notebook
    try:
        same = output.resolve() == live_notebook.resolve()
    except OSError:
        same = output == live_notebook
    if not same and output.exists() and live_notebook.exists():
        try:
            same = os.path.samefile(output, live_notebook)
        except OSError:
            same = False
    if config is None or config.root_dir is None:
        source_names = {notebook.name}
        try:
            source_names.add(notebook.resolve().name)
            output_names = {output.name, output.resolve().name}
        except OSError:
            output_names = {output.name}
        same = same or bool(source_names & output_names)
    if same:
        raise NotebookError("export refuses to overwrite the live notebook source")
    return output


async def _open_model(config: ServerConfig, notebook: str, timeout: float) -> Any:
    _, _, NbModelClient, get_notebook_websocket_url = _optional_dependencies()
    model: Any | None = None
    try:
        websocket_url = get_notebook_websocket_url(config.url, notebook, token=config.token)
        model = NbModelClient(
            websocket_url,
            path=notebook,
            username="report-notebook-cli",
            timeout=timeout,
            ws_max_body_size=MAX_WEBSOCKET_BODY_SIZE,
        )
        await asyncio.wait_for(model.start(), timeout=timeout)
        await asyncio.wait_for(model.wait_until_synced(), timeout=timeout)
    except asyncio.TimeoutError as error:
        if model is not None:
            await _best_effort_stop_model(model, timeout)
        raise NotebookError(f"timed out connecting to live notebook: {notebook}") from error
    except NotebookError:
        raise
    except Exception as error:
        if model is not None:
            await _best_effort_stop_model(model, timeout)
        raise NotebookError(f"could not connect to live notebook: {notebook}") from error
    return model


async def _best_effort_stop_model(model: Any, timeout: float) -> None:
    """Stop a partially initialized model without extending a failed command."""

    cleanup_timeout = min(max(timeout, 0.1), 5.0)
    try:
        await asyncio.wait_for(model.stop(), timeout=cleanup_timeout)
    except Exception:
        return


async def _close_model(model: Any, timeout: float) -> None:
    """Close a normal model and report when its final flush is unconfirmed."""

    cleanup_timeout = min(max(timeout, 0.1), 5.0)
    try:
        await asyncio.wait_for(model.stop(), timeout=cleanup_timeout)
    except asyncio.TimeoutError as error:
        raise NotebookError(
            "live notebook close timed out; final document sync is unconfirmed"
        ) from error
    except Exception as error:
        raise NotebookError(
            "live notebook close failed; final document sync is unconfirmed"
        ) from error


async def _with_model(config: ServerConfig, notebook: str, timeout: float, operation: Callable[[Any], Any]) -> Any:
    model = await _open_model(config, notebook, timeout)
    operation_error: BaseException | None = None
    try:
        return await operation(model)
    except BaseException as error:
        operation_error = error
        raise
    finally:
        try:
            await _close_model(model, timeout)
        except NotebookError as close_error:
            if operation_error is None:
                raise
            operation_error.add_note(str(close_error))


async def read_live(config: ServerConfig, notebook: str, selector: str | None, timeout: float) -> dict[str, Any]:
    async def operation(model: Any) -> dict[str, Any]:
        indexes = range(len(model)) if selector is None else [cell_index(model, selector)]
        return {
            "notebook": notebook,
            "cells": [serialise_cell(model, index) for index in indexes],
        }

    return await _with_model(config, notebook, timeout, operation)


async def update_live(
    config: ServerConfig, notebook: str, selector: str, source: str, timeout: float
) -> dict[str, Any]:
    async def operation(model: Any) -> dict[str, Any]:
        index = cell_index(model, selector)
        old_source = model.get_cell_source(index)
        model.set_cell_source(index, source)
        await asyncio.sleep(0.05)
        return {"notebook": notebook, "changed": old_source != source, "cell": serialise_cell(model, index)}

    return await _with_model(config, notebook, timeout, operation)


async def insert_live(
    config: ServerConfig,
    notebook: str,
    index: int,
    source: str,
    cell_type: str,
    stable_name: str | None,
    timeout: float,
) -> dict[str, Any]:
    async def operation(model: Any) -> dict[str, Any]:
        actual_index = len(model) if index == -1 else index
        if actual_index < 0 or actual_index > len(model):
            raise NotebookError(f"insert index is outside the notebook: {index}")
        metadata = {"collaboration": {"stable_name": stable_name}} if stable_name else None
        kwargs = {"metadata": metadata} if metadata else {}
        model.insert_cell(actual_index, source, cell_type, **kwargs)
        await asyncio.sleep(0.05)
        return {"notebook": notebook, "cell": serialise_cell(model, actual_index)}

    return await _with_model(config, notebook, timeout, operation)


async def delete_live(config: ServerConfig, notebook: str, selector: str, timeout: float) -> dict[str, Any]:
    async def operation(model: Any) -> dict[str, Any]:
        index = cell_index(model, selector)
        deleted = _json_ready(dict(model.delete_cell(index)))
        await asyncio.sleep(0.05)
        return {"notebook": notebook, "deleted": deleted, "index": index}

    return await _with_model(config, notebook, timeout, operation)


async def move_live(
    config: ServerConfig, notebook: str, selector: str, destination: int, timeout: float
) -> dict[str, Any]:
    async def operation(model: Any) -> dict[str, Any]:
        index = cell_index(model, selector)
        if destination < -1:
            raise NotebookError("move destination must be -1 or a non-negative index")
        if destination >= len(model):
            raise NotebookError(f"move destination is outside the notebook: {destination}")
        cell = _json_ready(dict(model[index]))
        model.delete_cell(index)
        final_index = len(model) if destination == -1 else destination
        model.insert(final_index, cell)
        await asyncio.sleep(0.05)
        return {
            "notebook": notebook,
            "from_index": index,
            "to_index": final_index,
            "cell": serialise_cell(model, final_index),
        }

    return await _with_model(config, notebook, timeout, operation)


async def execute_live(
    config: ServerConfig,
    notebook: str,
    selectors: Sequence[str],
    kernel_id: str | None,
    timeout: float,
) -> dict[str, Any]:
    requests, JupyterKernelClient, _, _ = _optional_dependencies()
    session = session_for(config, notebook, requests=requests, timeout=timeout)
    resolved_kernel_id = kernel_id or _session_kernel_id(session)
    if not resolved_kernel_id:
        raise NotebookError("no running kernel session for this notebook; open it in JupyterLab first")

    async def operation(model: Any) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        with JupyterKernelClient(
            server_url=config.url, token=config.token, kernel_id=resolved_kernel_id
        ) as kernel:
            for selector in selectors:
                index = cell_index(model, selector)
                source_before = model.get_cell_source(index)
                result = await asyncio.to_thread(
                    model.execute_cell, index, kernel, timeout=timeout
                )
                source_after = model.get_cell_source(index)
                results.append(
                    {
                        "cell": serialise_cell(model, index),
                        "result": _json_ready(result),
                        "executed_source_sha256": sha256_text(source_before),
                        "source_sha256_after": sha256_text(source_after),
                        "source_executed_hash_mismatch": source_before != source_after,
                    }
                )
        failed = any(
            item.get("result", {}).get("status") == "error" for item in results
        )
        return {
            "notebook": notebook,
            "kernel_id": resolved_kernel_id,
            "results": results,
            "status": "error" if failed else "ok",
        }

    return await _with_model(config, notebook, timeout, operation)


def _kernel_id(kernel: Any) -> str | None:
    manager = getattr(kernel, "_manager", None)
    model = getattr(manager, "kernel", None)
    return model.get("id") if isinstance(model, Mapping) else None


def _eval_code(args: argparse.Namespace) -> str:
    value = getattr(args, "code", None)
    code_file = getattr(args, "code_file", None)
    if value is not None and code_file is not None:
        raise NotebookError("choose one of --code and --code-file")
    if code_file is not None:
        if code_file == "-":
            return sys.stdin.read()
        try:
            return Path(code_file).expanduser().read_text(encoding="utf-8")
        except OSError as error:
            raise NotebookError(f"code file cannot be read: {code_file}") from error
    if value is None:
        raise NotebookError("eval requires --code or --code-file")
    return value


def eval_code(
    config: ServerConfig,
    notebook: str,
    code: str,
    scope: str,
    kernel_id: str | None,
    timeout: float,
) -> dict[str, Any]:
    _, JupyterKernelClient, _, _ = _optional_dependencies()
    if scope == "shared" and not kernel_id:
        raise NotebookError("shared eval needs a running notebook kernel")
    if scope == "scratch" and kernel_id:
        raise NotebookError("scratch eval creates its own kernel; omit --kernel-id")
    kwargs: dict[str, Any] = {"server_url": config.url, "token": config.token}
    if kernel_id:
        kwargs["kernel_id"] = kernel_id
    with JupyterKernelClient(**kwargs) as kernel:
        result = kernel.execute(code, timeout=timeout)
        actual_kernel_id = kernel_id or _kernel_id(kernel)
    return {
        "notebook": notebook,
        "scope": scope,
        "kernel_id": actual_kernel_id,
        "result": _json_ready(result),
        "status": result.get("status", "ok") if isinstance(result, Mapping) else "ok",
        "scratch_cleanup": scope == "scratch",
    }


def status(config: ServerConfig, notebook: str, timeout: float) -> dict[str, Any]:
    requests, _, _, _ = _optional_dependencies()
    sessions_response = _request(requests, config, "GET", "/api/sessions", timeout=timeout)
    kernels_response = _request(requests, config, "GET", "/api/kernels", timeout=timeout)
    kernelspecs_response = _request(requests, config, "GET", "/api/kernelspecs", timeout=timeout)
    sessions = sessions_response.json()
    kernels = kernels_response.json()
    kernelspecs = kernelspecs_response.json().get("kernelspecs", {})
    session = next(
        (
            item
            for item in sessions
            if (item.get("path") or item.get("notebook", {}).get("path")) == notebook
        ),
        None,
    )
    kernel = session.get("kernel") if session else None
    kernel_name = kernel.get("name") if isinstance(kernel, Mapping) else None
    kernelspec = kernelspecs.get(kernel_name, {}) if kernel_name else {}
    return {
        "server_url": config.url,
        "notebook": notebook,
        "connected": True,
        "session": {
            "id": session.get("id") if session else None,
            "kernel_id": _session_kernel_id(session),
            "kernel_name": kernel_name,
            "kernel_status": (
                next((item.get("execution_state") for item in kernels if item.get("id") == _session_kernel_id(session)), None)
                if session
                else None
            ),
        },
        "session_count": len(sessions),
        "kernel_count": len(kernels),
        "kernelspec": {
            "name": kernel_name,
            "display_name": kernelspec.get("spec", {}).get("display_name"),
            "configured_argv": kernelspec.get("spec", {}).get("argv"),
        },
    }


async def export_live(
    config: ServerConfig, notebook: str, output: Path, format_name: str, timeout: float
) -> dict[str, Any]:
    def write_snapshot(model: Any) -> dict[str, Any]:
        snapshot = notebook_snapshot(model)
        output.parent.mkdir(parents=True, exist_ok=True)
        native = _native_notebook(snapshot)
        if format_name == "ipynb":
            import nbformat

            output.write_text(nbformat.writes(native, version=4), encoding="utf-8")
        elif format_name == "py":
            text = _jupytext().writes(native, fmt="py:percent")
            output.write_text(text, encoding="utf-8")
        else:
            raise NotebookError(f"unsupported export format: {format_name}")
        return {
            "notebook": notebook,
            "output": str(output),
            "format": format_name,
            "cells": len(snapshot["cells"]),
        }

    return await _with_model(config, notebook, timeout, lambda model: _sync(write_snapshot(model)))


async def _sync(value: Any) -> Any:
    return value


def _emit(result: Any, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(_json_ready(result), indent=2))
        return
    if isinstance(result, Mapping):
        print(f"Notebook: {result.get('notebook', '')}")
        if isinstance(result.get("cells"), list):
            for cell in result["cells"]:
                print(f"[{cell.get('index')}] {cell.get('stable_name') or cell.get('id') or cell.get('cell_type')}")
                print(cell.get("source", ""), end="" if str(cell.get("source", "")).endswith("\n") else "\n")
                mismatch = cell.get("source_executed_hash_mismatch")
                if mismatch is not None:
                    print(f"source/executed hash mismatch: {mismatch}")
                print(f"outputs: {len(cell.get('outputs', []))}")
        elif "output" in result:
            print(f"Exported {result.get('format')} snapshot: {result.get('output')}")
        elif isinstance(result.get("results"), list):
            print(f"Kernel: {result.get('kernel_id', '')} ({result.get('status', 'ok')})")
            for item in result["results"]:
                cell = item.get("cell", {})
                execution = item.get("result", {})
                print(
                    f"[{cell.get('index')}] {cell.get('stable_name') or cell.get('id') or cell.get('cell_type')} "
                    f"status={execution.get('status', 'unknown')} outputs={len(execution.get('outputs', []))} "
                    f"source_changed={item.get('source_executed_hash_mismatch', False)}"
                )
                for output in execution.get("outputs", []):
                    output_type = output.get("output_type", "output")
                    if output_type == "stream":
                        text = str(output.get("text", "")).replace("\n", " ")
                        print(f"  stream: {text[:240]}")
                    elif output_type == "error":
                        print(f"  error: {output.get('ename', 'Error')}: {output.get('evalue', '')}")
                    elif isinstance(output.get("data"), Mapping):
                        print(f"  {output_type}: MIME {', '.join(sorted(output['data']))}")
        elif isinstance(result.get("result"), Mapping):
            execution = result["result"]
            print(
                f"Kernel: {result.get('kernel_id', '')} scope={result.get('scope', '')} "
                f"status={result.get('status', execution.get('status', 'unknown'))}"
            )
            for output in execution.get("outputs", []):
                output_type = output.get("output_type", "output")
                if output_type == "stream":
                    text = str(output.get("text", "")).replace("\n", " ")
                    print(f"  stream: {text[:240]}")
                elif output_type == "error":
                    print(f"  error: {output.get('ename', 'Error')}: {output.get('evalue', '')}")
                elif isinstance(output.get("data"), Mapping):
                    print(f"  {output_type}: MIME {', '.join(sorted(output['data']))}")
        else:
            print(json.dumps(_json_ready(result), indent=2))
    else:
        print(result)


def command(args: argparse.Namespace) -> int:
    config = read_server(args.server_json)
    output_format = getattr(args, "output_format", "text")
    timeout = float(getattr(args, "timeout", DEFAULT_TIMEOUT))
    if args.operation == "status":
        result = status(config, args.notebook, timeout)
    elif args.operation == "read":
        result = asyncio.run(read_live(config, args.notebook, args.cell, timeout))
    elif args.operation == "edit":
        result = asyncio.run(
            update_live(config, args.notebook, args.cell, _source_from_args(args), timeout)
        )
    elif args.operation == "insert":
        result = asyncio.run(
            insert_live(
                config,
                args.notebook,
                args.index,
                _source_from_args(args),
                args.cell_type,
                args.stable_name,
                timeout,
            )
        )
    elif args.operation == "delete":
        result = asyncio.run(delete_live(config, args.notebook, args.cell, timeout))
    elif args.operation == "move":
        result = asyncio.run(move_live(config, args.notebook, args.cell, args.to, timeout))
    elif args.operation == "execute":
        result = asyncio.run(
            execute_live(config, args.notebook, args.cell, args.kernel_id, timeout)
        )
    elif args.operation == "eval":
        kernel_id = args.kernel_id
        if args.scope == "shared" and not kernel_id:
            requests, _, _, _ = _optional_dependencies()
            kernel_id = _session_kernel_id(
                session_for(config, args.notebook, requests=requests, timeout=timeout)
            )
        result = eval_code(config, args.notebook, _eval_code(args), args.scope, kernel_id, timeout)
    elif args.operation == "export":
        output = _output_path(args, config)
        result = asyncio.run(
            export_live(config, args.notebook, output, args.format, timeout)
        )
    else:
        raise NotebookError(f"unknown notebook operation: {args.operation}")
    _emit(result, output_format)
    if isinstance(result, Mapping) and result.get("status") == "error":
        return 1
    return 0


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--source", help="cell source text")
    source.add_argument("--source-file", help="read cell source from a UTF-8 file, or '-' for stdin")


def add_parser(parent: argparse._SubParsersAction) -> None:
    notebook = parent.add_parser(
        "notebook",
        help="inspect and collaborate on a live Jupyter notebook",
        description="Operate on the live notebook document and its running kernel.",
    )
    notebook.add_argument("--server-json", type=Path, required=True, help="Jupyter server credential JSON")
    notebook.add_argument("--notebook", default="report.ipynb", help="server-relative notebook path")
    notebook.add_argument("--output-format", choices=("text", "json"), default="text")
    notebook.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="bounded server or kernel timeout in seconds")
    subcommands = notebook.add_subparsers(dest="operation", required=True)

    status_parser = subcommands.add_parser("status", help="show server, session, and kernel status")
    status_parser.set_defaults(handler=command)

    read = subcommands.add_parser("read", help="read all cells or one selected cell")
    read.add_argument("--cell", help="cell index, native id, or collaboration stable name")
    read.set_defaults(handler=command)

    insert = subcommands.add_parser("insert", help="insert a cell")
    insert.add_argument("--index", type=int, default=-1, help="zero-based insertion index; -1 appends")
    insert.add_argument("--cell-type", choices=("code", "markdown", "raw"), default="code")
    insert.add_argument("--stable-name", help="optional collaboration stable name")
    _add_source_arguments(insert)
    insert.set_defaults(handler=command)

    update = subcommands.add_parser("edit", help="replace one cell's source")
    update.add_argument("--cell", required=True, help="cell index, native id, or stable name")
    _add_source_arguments(update)
    update.set_defaults(handler=command)

    delete = subcommands.add_parser("delete", help="delete one cell")
    delete.add_argument("--cell", required=True, help="cell index, native id, or stable name")
    delete.set_defaults(handler=command)

    move = subcommands.add_parser("move", help="move one cell while preserving its native id")
    move.add_argument("--cell", required=True, help="cell index, native id, or stable name")
    move.add_argument("--to", type=int, required=True, help="final zero-based index; -1 appends")
    move.set_defaults(handler=command)

    execute = subcommands.add_parser("execute", help="execute selected cells in the shared notebook kernel")
    execute.add_argument("--cell", action="append", required=True, help="cell selector; repeat for sequence")
    execute.add_argument("--kernel-id", help="explicit running kernel id")
    execute.set_defaults(handler=command)

    evaluate = subcommands.add_parser("eval", help="evaluate code in the shared or a new scratch kernel")
    scope = evaluate.add_mutually_exclusive_group(required=True)
    scope.add_argument("--shared", dest="scope", action="store_const", const="shared")
    scope.add_argument("--scratch", dest="scope", action="store_const", const="scratch")
    evaluate.add_argument("--kernel-id", help="explicit kernel id for shared evaluation")
    code = evaluate.add_mutually_exclusive_group(required=False)
    code.add_argument("--code", help="code text")
    code.add_argument("--code-file", help="read UTF-8 code from a file, or '-' for stdin")
    evaluate.set_defaults(handler=command)

    export = subcommands.add_parser("export", help="export one live snapshot without overwriting the source")
    export.add_argument("--format", choices=("ipynb", "py"), required=True)
    export.add_argument("--output", required=True, help="explicit local output path")
    export.set_defaults(handler=command)
