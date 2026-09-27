# Reporting tools

This component owns the report CLI, report artifact inspection, browser
verification, and shared presentation helpers. Its Python project and tests are
independent of the repository's notebook environments and research examples.
Stage: sharing, with presentation helpers in consolidation.

Use the tools from a clone of this repository. The [repository guide](../../README.md#use-reporting-tools)
owns setup and commands. Run commands there from the repository root; uv selects
this component with `--project components/reporting`.

The [report contract](../../docs/report-contract.md),
[CLI design](../../docs/report-cli-design.md), and
[presentation guide](../../.agents/skills/report-presentation/SKILL.md) own the relevant design
boundaries. Source is in `src/executable_reports/`; tests are in `tests/`.

The optional `notebook` extra installs the agent-side live notebook clients,
Jupytext, and HTTP transport used by `report notebook`:

```sh
uv sync --project components/reporting --extra notebook
```

The extra does not install JupyterLab. Install the host and its renderer from
the [notebook environment guide](../../environments/README.md).
