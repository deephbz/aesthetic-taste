---
purpose: Give report and component authors shared terms and responsibility boundaries.
owns: Report vocabulary, the three-level analysis stack, and shared design forces.
does-not-own: Authoring procedures, component implementation, or published-report guarantees.
stage: shaping
status: active
---

# Report model

Read this model when structuring report code or designing reusable analysis.
The [report-authoring skill](../.agents/skills/report-authoring/SKILL.md) owns
orchestration and live editing. The
[analysis-components skill](../.agents/skills/analysis-components/SKILL.md) owns
the reusable component contract and design procedure. For meaning and
computation inside dataframe-centric components, use
[dataframe-pipelines](../.agents/skills/dataframe-pipelines/SKILL.md). The
[report contract](report-contract.md) owns observable report guarantees.

## Forces

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
| **Reusable analysis component** | Layer 2: maintained code with a reusable, composable public contract for loading, normalization, computation, or visualization. |
| **Report orchestration** | Layer 3: notebook code that binds sources, configures components, and lays out sections. |
| **Dashboard report** | A Layer 3 form the user directs. The user selects data, parameters, and views. Interpretation stays with the user. |
| **Narrative report** | A Layer 3 form the author fixes at a point in time: inputs, evidence order, presentation, and conclusions. |
| **Global setup** | Section 0. Imports, definitions, functions, constants, and configuration shared by more than one section. |
| **Report configuration** | Structured values shared by all sections. Global setup owns them. |
| **Report section** | One orchestration unit with an explicit dependency boundary. It has its own setup, wiring, and display. |
| **Section entry point** | The one visible, parameterized operation that a section's wiring calls. |
| **Setup, wiring, display** | The three responsibilities of report code, at notebook level and at section level. |
| **Input model** | The meaning and requirements of a component's inputs. For dataframe inputs, this includes dataset role, grain, and field roles rather than literal source names. |
| **Field binding** | The caller-declared mapping from a physical source field to a semantic field role. |
| **Source adapter** | Report-specific Layer 3 wiring that binds a chosen source to an input model; it can call reusable loading or normalization components. |
| **Projection** | A chart, table, or summary derived from computed results. Never a second data authority. |

“Layer” names only the three-level stack. Component boundaries describe inputs,
configuration, outputs, and observable behavior. Specialized skills guide the
internals of particular component kinds. “Stage” keeps its lifecycle meaning
(shaping, exploration, consolidation, hardening, sharing).

## Structure

```text
Analysis report
├── Layer 3 — Report orchestration                    report-authoring skill
│   ├── global setup (Section 0): shared imports, definitions, configuration
│   ├── source adapters + field bindings
│   ├── report sections, each: setup → wiring → display
│   └── form: dashboard report | narrative report
├── Layer 2 — Reusable analysis components            analysis-components skill
│   └── declared inputs + configuration → [reusable capability] → outputs
└── Layer 1 — Generic analysis tooling                outside this contract
```

The report (Layer 3) selects sources, supplies bindings and configuration, and
connects components (Layer 2). Components can consume other components' outputs;
their internals use generic tooling (Layer 1). The report arranges displayable
outputs into sections and supplies the narrative.

