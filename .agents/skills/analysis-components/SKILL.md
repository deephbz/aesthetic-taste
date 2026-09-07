---
name: analysis-components
description: Design or revise reusable analysis components for composition and reuse. Use for component responsibility, input and output contracts, configuration, reuse, and report integration.
---

# Analysis components

Own the external Layer 2 component contract, its composability and reusability,
and its relationship with Layer 3 reports. A component can load data, normalize
it, compute a result, or produce a visualization. It need not do all four.
Stage: shaping. Status: active. The repository has no settled component catalog.

A caller relies on the public contract: purpose, input requirements,
configuration, output meaning, and observable behavior. Internal stages,
algorithms, query plans, concrete API syntax, and library choices belong to the
implementation or a more specialized design discipline.

Read the [report model](../../../docs/report-model.md) for the shared vocabulary
and stack. Use [report-authoring](../report-authoring/SKILL.md) when wiring
components into report sections. A component can be used without a report.

When designing a dataframe-centric component, use
[dataframe-pipelines](../dataframe-pipelines/SKILL.md) for guidance inside the
component: meaning, validation scope, computation, and inspection. For table
outputs, use [table-presentation](../table-presentation/SKILL.md).

## Layer 2 component contract

Give the component one coherent responsibility. Several related outputs can
serve that responsibility. Put enough behavior behind the boundary that callers
can reuse it without absorbing its implementation.

State the meaning and requirements of inputs and outputs, and the configuration
that changes the intended behavior. State relevant failures, external effects,
and dependencies. Choose the public operations and configuration representation
to fit the responsibility.

## Compose through meaning

A producer's output must satisfy its consumer's input contract. Matching field
names or physical types alone does not establish that fit. Make required
adaptation explicit and preserve the intended meaning through composition.

## Keep outputs inspectable and reproducible

Declare the inputs, source identity, configuration, and external dependencies
needed to explain or reproduce an output. Keep important results inspectable.
A rendered chart alone is not the authority. For reports, the
[report contract](../../../docs/report-contract.md) owns the required guarantees.

## Keep component and report responsibilities distinct

The component owns the behavior and output semantics promised by its contract.
The report chooses concrete sources, configures and connects components, orders
sections, arranges outputs, and supplies narrative conclusions.

Reusable data loading and normalization can be components themselves.
Report-specific source selection and bindings remain visible in Layer 3; they
may call those components. Source adapters normalize what the consumer contract
requires; domain aggregation belongs in an explicit computation component or
visible section wiring. Resolve field meaning explicitly rather than guessing it.
A component receives the configuration its own contract needs, rather than the
complete report configuration.

## Shape reuse from a concrete request

1. Name the useful responsibility and the inputs and outputs it needs.
2. Separate stable meaning from details that vary between actual uses.
3. Expose choices that callers need to change through the public contract.
   Keep implementation choices behind the boundary.
4. Confirm the proposed decomposition against the requester's uses, including
   the first concrete request. Narrow or extend it before building.

Use demonstrated variation to guide reuse. A one-off layout or report passage
can stay in the report; repeated loading, normalization, computation, or display
behavior can justify a component. For a concrete visualization example, read
[shaping a visualization component](references/visualization-example.md).

When integrating a component into a report, preserve the
[one-edit locality rule](../report-authoring/SKILL.md#5-wrap-only-as-deep-as-one-edit-can-reach).
That is a constraint on report integration, not a required component architecture.

## Completion

Record the responsibility, input and output meaning, caller-controlled choices,
and relevant observable behavior. Check the first requested use and each claimed
composition at the public boundary. Keep unresolved input meaning explicit;
implementation detail or visual polish does not establish the contract.
