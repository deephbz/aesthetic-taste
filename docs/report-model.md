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
the reusable component contract and design procedure. The
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
├── Layer 3 — Report orchestration                    report-authoring skill
│   ├── global setup (Section 0): shared imports, definitions, configuration
│   ├── source adapters + field bindings
│   ├── report sections, each: setup → wiring → display
│   └── form: dashboard report | narrative report
├── Layer 2 — Reusable analysis components            analysis-components skill
│   └── component = input model → computation → presentation → projections
└── Layer 1 — Generic analysis tooling                outside this contract
```

Execution flows: source data → source adapter + bindings (Layer 3) →
component (Layer 2) → projections → section layout (Layer 3).

