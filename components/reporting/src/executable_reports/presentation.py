"""Reusable Quarto reading defaults, not report data or renderer policy.

The contract is in docs/report-contract.md; usage and ownership are in
.agents/skills/report-presentation/SKILL.md. New reports receive editable source snapshots.
Existing reports can reference these assets from their versioned source bundle.
"""
from importlib.resources import files


def reading_navigation() -> str:
    """Return the inline navigation asset; no external runtime is required."""
    return files("executable_reports").joinpath("presentation_assets/reading-navigation.html").read_text(encoding="utf-8")


def reading_frontmatter() -> str:
    """Return a raw Jupytext cell carrying Quarto's reading format defaults."""
    yaml = files("executable_reports").joinpath("presentation_assets/reading-format.yml").read_text(encoding="utf-8")
    return "# %% [raw]\n# ---\n" + "".join("# " + line + "\n" for line in yaml.splitlines()) + "# ---\n\n"


class Mermaid:
    """One Mermaid source displayed through the native notebook MIME hook.

    No frontend rendering is needed before export. report render projects the
    native MIME output into Quarto Mermaid cells. See the presentation
    guide for export format and normal notebook trust requirements.
    """

    def __init__(self, source: str):
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Mermaid source must be nonempty text")
        self.source = source

    def _repr_mimebundle_(self, include=None, exclude=None):
        bundle = {"text/vnd.mermaid": self.source, "text/plain": self.source}
        return {key: value for key, value in bundle.items()
                if (include is None or key in include) and (exclude is None or key not in exclude)}


def quarto_notebook(notebook: dict) -> dict:
    """Project native Mermaid outputs into Quarto blocks without changing evidence.

    This is an export adapter, not an execution pass. The caller must render the
    returned copy and retain the original executed notebook as the source record.
    """
    from copy import deepcopy
    import re
    projected = deepcopy(notebook)
    cells = []
    for cell in projected.get("cells", []):
        if cell.get("cell_type") != "code":
            cells.append(cell)
            continue
        outputs = cell.get("outputs", [])
        pending = dict(cell, outputs=[])
        for output in outputs:
            data = output.get("data", {})
            if "text/vnd.mermaid" not in data:
                pending["outputs"].append(output)
                continue
            if pending.get("source") or pending["outputs"]:
                cells.append(pending)
            source = data["text/vnd.mermaid"]
            if isinstance(source, list):
                source = "".join(source)
            fence = "`" * max(3, max((len(m.group()) + 1 for m in re.finditer(r"`+", source)), default=0))
            cells.append({"cell_type": "markdown", "metadata": {},
                          "source": f"{fence}{{mermaid}}\n{source}\n{fence}".splitlines(keepends=True)})
            pending = {"cell_type": "code", "metadata": {"echo": False}, "source": [],
                       "execution_count": None, "outputs": []}
        if pending.get("source") or pending["outputs"] or not outputs:
            cells.append(pending)
    projected["cells"] = cells
    return projected
