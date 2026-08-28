"""Stage the charting example's generated static deployment for GitHub Pages."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
EXAMPLE = REPOSITORY / "examples" / "charting-api-philosophy"
SITE = REPOSITORY / "_site"

FILES = {
    EXAMPLE / "report.rendered.html": SITE / "index.html",
    EXAMPLE / "report.inspect.html": SITE / "report.inspect.html",
    EXAMPLE / "report.inventory.json": SITE / "report.inventory.json",
    EXAMPLE / "data" / "markouts.arrow": SITE / "data" / "markouts.arrow",
}
DIRECTORIES = {
    EXAMPLE / "report.static": SITE / "report.static",
    EXAMPLE / "styles": SITE / "styles",
    EXAMPLE / "artifacts": SITE / "artifacts",
}


def main() -> None:
    if SITE.exists():
        raise SystemExit(f"staging directory already exists: {SITE}")
    missing = [
        str(path.relative_to(REPOSITORY))
        for path in (*FILES, *DIRECTORIES)
        if not path.exists()
    ]
    if missing:
        raise SystemExit("missing deployment artifacts: " + ", ".join(missing))
    SITE.mkdir()
    for source, target in FILES.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for source, target in DIRECTORIES.items():
        shutil.copytree(source, target)
    manifest = {
        "site": str(SITE.relative_to(REPOSITORY)),
        "files": sum(1 for path in SITE.rglob("*") if path.is_file()),
        "bytes": sum(path.stat().st_size for path in SITE.rglob("*") if path.is_file()),
    }
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
