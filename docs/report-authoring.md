---
purpose: Define the structure of report code. The report and its notebook are
  a white box here.
owns: Layer 3 report code (global setup, sections, wiring, display), the
  external contract of reusable Layer 2 components, and the procedure for
  turning a concrete request into a component.
does-not-own: Deployment shape, data and view-state authority, parity, and
  durability (report-contract.md); component implementation, concrete APIs,
  and library choices (Layer 1); artifact names and build behavior
  (report-cli-design.md); the live authoring loop (SKILL.md).
stage: shaping. No reusable Layer 2 component exists yet; the contract has no
  worked example.
status: active
---

# Report authoring

## Forces

This document looks inside the report. [The report contract](report-contract.md)
treats it as a black box.

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
| **Global setup** | Section 0. Imports, definitions, functions, constants, and configuration shared by more than one section. |
| **Report configuration** | Structured values shared by all sections. Global setup owns them. |
| **Report section** | One orchestration unit with an explicit dependency boundary. It has its own setup, wiring, and display. |
| **Section entry point** | The one visible, parameterized operation that a section's wiring calls. |
| **Setup, wiring, display** | The three responsibilities of report code, at notebook level and at section level. |
| **Input model** | A component's semantic contract: dataset role, grain, and field roles with meaning. Not literal column names. |
| **Field binding** | The caller-declared mapping from a physical source field to a semantic field role. |
| **Source adapter** | Thin Layer 3 code that binds external data to an input model. |
| **Projection** | A chart, table, or summary derived from computed results. Never a second data authority. |

“Layer” names only the three-level stack. The component contract has three
parts: input model, computation, presentation. “Stage” keeps its lifecycle
meaning (shaping, exploration, consolidation, hardening, sharing) and is not
used for contract parts.

## Structure

```text
Analysis report
├── Layer 3 — Report orchestration                    governed here
│   ├── global setup (Section 0): shared imports, definitions, configuration
│   ├── source adapters + field bindings
│   ├── report sections, each: setup → wiring → display
│   └── form: dashboard report | narrative report
├── Layer 2 — Reusable analysis components            contract governed here
│   └── component = input model → computation → presentation → projections
└── Layer 1 — Generic analysis tooling                not governed here
```

Execution flows: source data → source adapter + bindings (Layer 3) →
component (Layer 2) → projections → section layout (Layer 3).

## Report structure rules

These rules apply to dashboard reports and narrative reports. A narrative
report can fix inputs, order, chart settings, and conclusions, because those
fixed choices are its accepted point-in-time result. Its code still follows
the same structure. Thin, visible orchestration makes human-agent handoff
easy. A human changes a parameter or moves a projection without entering
component internals. An agent finds the affected section without
reconstructing hidden notebook state.

1. **Three responsibilities, at two levels.** Report code does three things:
   setup (imports, definitions, functions, constants, configuration), wiring
   (source → adapter and bindings → component → projections), and display
   (the calls that render projections into output cells). The notebook as a
   whole has a global setup section, then sections that wire and display.
   Each section repeats the pattern: its own setup, then its wiring, then its
   display, in that order and visibly.

2. **Locality decides where a definition lives.** Anything used by more than
   one section lives in global setup: shared imports, shared helper
   functions, shared constants, the report configuration. Anything used by
   one section lives under that section's heading: its imports, its helper
   functions, its constants, its parameters. Do not leak a section-local
   definition into global setup, and do not redefine a shared value locally.
   A free-floating constant at module scope that only one section reads is a
   hidden dependency. The same rule holds for a helper function.

3. **Keep section dependencies local and visible.** Each Section N takes one
   of two forms. It depends only on global setup plus its local setup and
   source inputs, or it consumes the explicit result of Section N−1. No
   section reads hidden state from an unrelated section. If many sections
   need one value, promote it to global setup.

4. **Expose one rich section entry point, configured by a dataclass.** Give
   each section one parameterized operation. Its configuration contains each
   choice that changes analytical or presentation intent, such as groupings,
   pivots, filters, measures, colour maps, and geometry. Put that
   configuration in a dataclass, not in a wide function signature: a
   dataclass with ten or twenty fields, grouped into nested dataclasses where
   the fields cluster, reads and edits better than the same values as
   positional or keyword arguments. One stable operation can accept one rich
   configuration. The same computed data can support many views.

5. **Wrap only as deep as one edit can reach.** Layers between the component
   API and the display call are allowed when they clarify composition. Each
   layer costs one hop for every change, and dashboard work is trial and
   error between a human and an agent: change one thing, rerun, look. The
   test: a reader changes one analytical or presentation choice by editing
   one field in one place and rerunning one cell. If a change requires edits
   in several functions across several layers, the wrapping is too deep.
   Flatten it. Keep one-off layout and report text in the report; move a
   reused analytical perspective into Layer 2.

6. **Bind each widget to one configuration field.** In a dashboard report,
   each widget reads and writes one named field, so the same state can be
   inspected or replayed without the widget runtime. Keep that state
   renderer-independent, as [the report contract](report-contract.md)
   requires.

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
   as [the report contract](report-contract.md) requires. A rendered chart alone is
   not the authority.

5. **The component owns presentation semantics; the report owns layout and
   conclusions.** The component's charts and tables express its analytical
   perspective. Component configuration controls meaningful presentation
   choices. The report controls section order, neighboring components,
   narrative text, and conclusions. Do not pass the complete report
   configuration into a component.

## From a concrete request to a component

A request usually arrives as one concrete case: "plot the number of resting
orders at each price level, price on the y axis, time on the x axis, one
horizontal element per level, coloured by order count." Code written for
exactly that case is a one-off. The next request ("colour by notional
instead", "make the bars thinner", "add a second book") means rewriting it.

Before writing the component, decompose the request and confirm the intended
use with the person who asked:

1. **Name the decomposable elements.** In the example: a per-level geometry
   (horizontal elements placed by price and time), a style mapping from one
   scalar per level per timestamp to a colour, and an input payload per price
   level that carries the order count today and can carry other fields
   later.
2. **Generalize the input model, not the visual.** The payload is the
   semantic input model of the component (dataset role: book levels; grain:
   one row per level per timestamp; field roles: price, time, one or more
   measures). The visual is fixed; which measure drives the style mapping is
   configuration.
3. **Put every choice a user will want to change into the configuration.**
   Colour map, element height, which measure maps to colour, axis ranges. The
   first request is one point in that configuration space.
4. **Ask which of these the requester actually needs.** State the
   decomposition in a few lines and the use cases it would cover. The
   requester confirms, narrows, or extends. Then build the decomposed version
   configured to the first request.

Decomposition is not licence to build a framework. Rule 5 still applies: the
result is one component with one entry point and one configuration
dataclass, and the concrete request is satisfied by one wiring call in one
section.
