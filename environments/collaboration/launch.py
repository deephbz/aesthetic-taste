"""Start a local JupyterLab host for live notebook collaboration.

The host environment owns this launcher. The notebook root and runtime
directory are caller-selected. The runtime directory contains the private
server connection record and all generated Jupyter state.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
from pathlib import Path

from traitlets.config import Config


PAGE_CONFIG = Path(__file__).with_name("page_config.json")
SERVER_HOST = "127.0.0.1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start a local JupyterLab host for live notebook collaboration."
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        required=True,
        help="directory served as the notebook root",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        required=True,
        help="ignored directory for Jupyter state and server.json",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8896,
        help="localhost port (default: 8896)",
    )
    return parser


def _runtime_environment(runtime: Path) -> dict[str, Path]:
    runtime.mkdir(parents=True, exist_ok=True)
    runtime.chmod(0o700)
    paths = {
        "JUPYTER_CONFIG_DIR": runtime / "jupyter-config",
        "JUPYTER_DATA_DIR": runtime / "jupyter-data",
        "JUPYTER_RUNTIME_DIR": runtime / "jupyter-runtime",
        "XDG_CACHE_HOME": runtime / "cache",
        "MPLCONFIGDIR": runtime / "mpl",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
    return paths


def _write_page_config(config_dir: Path) -> None:
    if not PAGE_CONFIG.is_file():
        raise RuntimeError(f"missing tracked Lab page config: {PAGE_CONFIG}")
    destination = config_dir / "labconfig" / "page_config.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PAGE_CONFIG, destination)


def _write_server_record(runtime: Path, root: Path, port: int, token: str) -> Path:
    location = runtime / "server.json"
    record = json.dumps(
        {
            "url": f"http://{SERVER_HOST}:{port}",
            "token": token,
            "root_dir": str(root),
            "port": port,
        },
        indent=2,
    ) + "\n"
    if location.exists():
        location.chmod(0o600)
    descriptor = os.open(location, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(record)
    location.chmod(0o600)
    return location


def main() -> None:
    args = _parser().parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")

    root = args.root_dir.expanduser().resolve()
    runtime = args.runtime_dir.expanduser().resolve()
    if root == runtime:
        raise SystemExit("--runtime-dir must differ from --root-dir")
    if runtime.is_relative_to(root):
        raise SystemExit("--runtime-dir must be outside --root-dir")
    root.mkdir(parents=True, exist_ok=True)

    paths = _runtime_environment(runtime)
    _write_page_config(paths["JUPYTER_CONFIG_DIR"])
    for variable, path in paths.items():
        os.environ[variable] = str(path)

    token = secrets.token_urlsafe(32)
    server_record = _write_server_record(runtime, root, args.port, token)

    from jupyter_server.serverapp import ServerApp

    config = Config()
    config.IdentityProvider.token = token
    config.LabApp.collaborative = True
    app = ServerApp(
        config=config,
        ip=SERVER_HOST,
        port=args.port,
        port_retries=0,
        root_dir=str(root),
        open_browser=False,
        allow_remote_access=False,
        jpserver_extensions={
            "jupyter_server_ydoc": True,
            "jupyter_server_nbmodel": True,
            "jupyterlab": True,
        },
    )
    app.initialize([])
    print(f"JUPYTER_COLLAB_URL=http://{SERVER_HOST}:{args.port}/lab", flush=True)
    print(f"JUPYTER_SERVER_JSON={server_record}", flush=True)
    app.start()


if __name__ == "__main__":
    main()
