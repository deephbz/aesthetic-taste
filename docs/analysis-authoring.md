---
purpose: Define technology-neutral boundaries for report orchestration and the
  caller-visible contract of reusable analysis components.
scope: Owns Layer 3 report code and the external Layer 2 contract. Rendering
  parity, view-state authority, artifacts, publication, and the live workflow
  belong to the linked documents.
status: active
---

# Analysis authoring principles

## Purpose and forces

This document governs report orchestration code and the external contract that
reports require from reusable analysis components. It does not govern component
implementation, concrete APIs, or library choices. [The report
principles](principles.md) own rendering parity, data and view-state authority,
and durability. [The CLI design](report-cli-design.md) owns artifact names and
build behavior. [The collaboration guide](SKILL.md) owns the live authoring and
serving loop.

Four forces shape these rules. Analysis is trial and error, so questions,
parameters, and useful views change often. Source data is messy and externally
controlled, so no single physical schema is possible. Concrete tools change
quickly, so only semantic boundaries stay stable. Agents make implementation
cheap, so readable intent and safe edit surfaces are the scarce resources.
When a force changes, the rules can change.

## Terminology

| Term | Meaning |
|---|---|
| **Generic analysis tooling** | Layer 1: domain-neutral data, computation, and visualization libraries. |
| **Reusable analysis component** | Layer 2: maintained code that turns a semantic input model into projections through one analytical perspective. |
| **Report orchestration** | Layer 3: notebook code that binds sources, configures components, and lays out sections. |
| **Dashboard report** | A Layer 3 form the user directs. The user selects data, parameters, and views. Interpretation stays with the user. |
| **Narrative report** | A Layer 3 form the author fixes at a point in time: inputs, evidence order, presentation, and conclusions. |
| **Report configuration** | Structured values shared by all sections. Section 0 owns them. |
| **Report section / entry point** | One orchestration unit with an explicit dependency boundary and one visible, parameterized operation. |
| **Input model** | A component's semantic contract: dataset role, grain, and field roles with meaning. Not literal column names. |
| **Field binding** | The caller-declared mapping from a physical source field to a semantic field role. |
| **Source adapter** | Thin Layer 3 code that binds external data to an input model. |
| **Projection** | A chart, table, or summary derived from computed results. Never a second data authority. |

“Layer” names only the three-level stack. “Stage” names the parts of the
component contract: input model, computation, presentation.

## Structure

```text
Analysis report
├── Layer 3 — Report orchestration                    governed here
│   ├── report configuration (Section 0)
│   ├── source adapters + field bindings
│   ├── report sections, each with one entry point
│   └── form: dashboard report | narrative report
├── Layer 2 — Reusable analysis components            contract governed here
│   └── component = input model → computation → presentation → projections
└── Layer 1 — Generic analysis tooling                not governed here
```

Execution flows: source data → source adapter + bindings (Layer 3) →
component (Layer 2) → projections → section layout (Layer 3).

## Dashboard report rules

These rules apply to dashboard reports. A narrative report can fix inputs,
order, chart settings, and conclusions, because those fixed choices are its
accepted point-in-time result. Thin, visible orchestration makes human-agent
handoff easy. A human changes a parameter or moves a projection without
entering component internals. An agent finds the affected section without
reconstructing hidden notebook state.

1. **Keep orchestration thin.** The notebook binds sources, configures
   components, and lays out projections. Move a reused analytical perspective
   into Layer 2. Keep one-off layout and report text in the report. A small
   helper call stack is acceptable when it clarifies composition, if the
   section entry point stays visible.

2. **Give every value one explicit owner.** Do not use free-floating global
   constants as dashboard runtime inputs, because they hide dependencies. Put
   values shared by all sections into the structured report configuration in
   Section 0. Put section-local values inside their section. Imports and
   reusable definitions can stay at module scope. The ban covers hidden runtime
   inputs, not normal language structure.

3. **Keep section dependencies local and visible.** Each Section N takes one
   of two forms. It depends only on Section 0 plus its local configuration and
   source inputs, or it consumes the explicit result of Section N−1. No section
   reads hidden state from an unrelated section. If many sections need one
   value, put it in the report configuration.

4. **Expose one rich section entry point.** Give each section one parameterized
   operation. Its structured configuration contains each choice that changes
   analytical or presentation intent, such as groupings, pivots, filters, and
   measures. A wide configuration does not require a wide API. One stable
   operation can accept one rich configuration. The same computed data can
   support many views.

5. **Bind each widget to one configuration field.** Each widget reads and
   writes one named field, so the same state can be inspected or replayed
   without the widget runtime. Keep that state renderer-independent, as [the
   report principles](principles.md) require.

## Layer 2 component contract

This section states what a report author can assume about a component. The
author must know the input contract and the promised output meaning. The author
must not need its algorithms, query plans, or renderer machinery. This
repository does not govern those implementation details. The contract has the
shape of a mini pipeline: semantic input model → computation → presentation.
This shape does not require one internal code architecture.

1. **One component, one analytical perspective.** A component can emit several
   related projections that support one perspective. It is a deep module: a
   small public surface over substantial computation and presentation. Reports
   can compose it without absorbing its internals.

2. **The input model is semantic.** The contract states dataset role,
   observation grain, required field roles, and types or units when the
   computation depends on them. It does not require literal source column
   names, because source data comes from systems outside the component's
   control. The caller satisfies the contract through field bindings:

   ```text
   dataset role: events            grain: one row per event
   semantic field: event_time      integer timestamp, declared time unit
   valid bindings: event_time ← time | t | update_timestamp
   ```

   The meaning is the contract. The source spelling is not. Semantic
   flexibility does not permit ambiguous data. A component can reject inputs
   whose meaning the caller cannot establish.

3. **Adapt sources in Layer 3, and keep adapters thin.** A source adapter loads
   external data, selects applicable records, declares field bindings, and
   normalizes only what the input model requires. It does not hide domain
   aggregation. The component does not discover files or guess column meaning.

4. **Results are a function of the contract.** Computed results depend on
   conforming inputs plus component configuration, so a report can rerun, test,
   and trace them. Important results stay inspectable through explicit inputs,
   as [the report principles](principles.md) require. A rendered chart alone is
   not the authority.

5. **The component owns presentation semantics; the report owns layout and
   conclusions.** The component's charts and tables express its analytical
   perspective. Component configuration controls meaningful presentation
   choices. The report controls section order, neighboring components,
   narrative text, and conclusions. Do not pass the complete report
   configuration into a component.
