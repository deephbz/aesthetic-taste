---
name: report-authoring
description: Structure or edit narrative and dashboard report code, including section dependencies, configuration, source wiring, and live notebook collaboration.
---

# Report authoring

Own report orchestration (Layer 3) and the live human-agent editing loop.
The report and notebook are a white box here. The [report contract](../../../docs/report-contract.md)
owns deployment shape, data and view-state authority, parity, and durability.
[CLI design](../../../docs/report-cli-design.md) owns artifact names and build behavior.
Component implementation, concrete APIs, and generic library choices remain
outside this skill's contract.
Stage: shaping for report structure; consolidation for live notebook collaboration.
Status: active. The reusable Layer 2 contract has no worked example yet.

## Start from the task

Read the [report model](../../../docs/report-model.md) for the shared vocabulary,
stack, and design forces. Read the [report contract](../../../docs/report-contract.md)
for data authority, state, host parity, and durability constraints.

- When consuming or designing a reusable component, read the
  [component contract](../analysis-components/SKILL.md#layer-2-component-contract).
  Use its design procedure only when creating or changing the component.
- When choosing data interchange, browser compute, or coordination technology,
  read [technology choices](references/technology-choices.md).
- Before creating or changing presentation configuration or display adapters,
  use [report-presentation](../report-presentation/SKILL.md).
- When creating or revising a table's structure, formats, or emphasis, use
  [table-presentation](../table-presentation/SKILL.md).
- When writing the prose a reader sees, use
  [report-writing](../report-writing/SKILL.md).
- When creating a new report root or producing saved outputs, use
  [report-delivery](../report-delivery/SKILL.md).

## Report structure rules

These rules apply to dashboard reports and narrative reports. A narrative
report can fix inputs, order, chart settings, and conclusions, because those
fixed choices are its accepted point-in-time result. Its code still follows
the same structure. Thin, visible orchestration makes human-agent handoff
easy. A human changes a parameter or moves a projection without entering
component internals. An agent finds the affected section without
reconstructing hidden notebook state.

### 1. Three responsibilities, at two levels

Report code does three things:
setup (imports, definitions, functions, constants, configuration), wiring
(source → adapter and bindings → component → projections), and display
(the calls that render projections into output cells). The notebook as a
whole has a global setup section, then sections that wire and display.
Each section repeats the pattern: its own setup, then its wiring, then its
display, in that order and visibly.

### 2. Locality decides where a definition lives

Anything used by more than
one section lives in global setup: shared imports, shared helper
functions, shared constants, the report configuration. Anything used by
one section lives under that section's heading: its imports, its helper
functions, its constants, its parameters. Do not leak a section-local
definition into global setup, and do not redefine a shared value locally.
A free-floating constant at module scope that only one section reads is a
hidden dependency. The same rule holds for a helper function.

### 3. Keep section dependencies local and visible

Each Section N takes one
of two forms. It depends only on global setup plus its local setup and
source inputs, or it consumes the explicit result of Section N−1. No
section reads hidden state from an unrelated section. If many sections
need one value, promote it to global setup.

### 4. Expose one rich section entry point, configured by a dataclass

Give
each section one parameterized operation. Its configuration contains each
choice that changes analytical or presentation intent, such as groupings,
pivots, filters, measures, colour maps, and geometry. Put that
configuration in a dataclass, not in a wide function signature: a
dataclass with ten or twenty fields, grouped into nested dataclasses where
the fields cluster, reads and edits better than the same values as
positional or keyword arguments. One stable operation can accept one rich
configuration. The same computed data can support many views.

### 5. Wrap only as deep as one edit can reach

Layers between the component
API and the display call are allowed when they clarify composition. Each
layer costs one hop for every change, and dashboard work is trial and
error between a human and an agent: change one thing, rerun, look. The
test: a reader changes one analytical or presentation choice by editing
one field in one place and rerunning one cell. If a change requires edits
in several functions across several layers, the wrapping is too deep.
Flatten it. Keep one-off layout and report text in the report; move a
reused analytical perspective into Layer 2.

### 6. Bind each widget to one configuration field

In a dashboard report,
each widget reads and writes one named field, so the same state can be
inspected or replayed without the widget runtime. Keep that state
renderer-independent, as [the report contract](../../../docs/report-contract.md)
requires.

## Iterate in a live notebook

The [live notebook collaboration guide](../../../docs/notebook-collaboration.md)
owns the human-agent session model and the `report notebook` command contract.
Use that guide when the task involves a running JupyterLab document or kernel.

1. Start from the notebook open in JupyterLab. Run `report notebook status` and
   `read` before editing.
2. Address cells by their stable IDs. Edit and execute only the changed cell or
   independent section when shared state is intentional.
3. Use the shared kernel to inspect existing variables and renderer state. Use
   `report notebook eval` with an isolated scratch kernel for experiments that
   must not change the shared namespace.
4. Read the live source and output after execution. A Python execution result
   does not prove that the browser displayed a rich MIME output.
5. Use `%autoreload 3` when reusable local modules change. Restart the kernel
   when selective execution leaves state provenance unclear.

The live `.ipynb` document is the editing authority during collaboration.
Jupytext `.py` is a one-way derived projection for review and version control.
Export it explicitly with `report notebook export`, or pass the native notebook
to the clean `report run --source` path. Use `report render` only with saved
outputs. Do not assume that editing the projection updates the live document.

Before release, use [report-delivery](../report-delivery/SKILL.md) for the clean
build and verification sequence.

## Coordinate human and agent edits

JupyterLab and the agent share one live document model. A human can edit or
execute a cell while the agent works. Read the current cell before replacing
it and inspect source and output together after execution. See the
[collaboration guide](../../../docs/notebook-collaboration.md) for accepted
same-cell, stale-output, and kernel-state limits.

Trust the notebook in JupyterLab before displaying browser-executable output.
The **Trust Notebook** command allows saved rich output such as Bokeh to run in
the browser. Trust is a browser execution decision, not a data or analytical
correctness check.

## Completion

Check that each section exposes its setup, wiring, and display. Trace its inputs
to global setup, local sources, or the explicit preceding result. Exercise the
changed section and confirm that one intended configuration edit reaches the
expected output in the live host. State any verification that remains
incomplete and link to the collaboration guide for known session limits.
