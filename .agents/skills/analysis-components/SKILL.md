---
name: analysis-components
description: Design or revise a reusable analysis component from a concrete analytical request. Use for semantic input models, field bindings, configuration, and projection ownership.
---

# Analysis components

Own the external Layer 2 component contract and the procedure for turning a
concrete request into one reusable analytical perspective. Algorithms, query
plans, concrete APIs, and generic library choices remain implementation concerns.
Stage: shaping. Status: active. No reusable Layer 2 component exists yet; this contract has no
worked example.

Read the [report model](../../../docs/report-model.md) for terms, shared design
forces, and the analysis stack. This skill can be used without creating a report.
When integrating a component into one, use
[report-authoring](../report-authoring/SKILL.md) for source adapters, section wiring,
and layout. For table projections, use [table-presentation](../table-presentation/SKILL.md).

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
   as [the report contract](../../../docs/report-contract.md) requires. A rendered chart alone is
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

Decomposition is not licence to build a framework. Keep one component with one
entry point and one configuration dataclass. When integrating it into a report,
apply the [one-edit locality rule](../report-authoring/SKILL.md#5-wrap-only-as-deep-as-one-edit-can-reach)
and satisfy the concrete request with one wiring call in one section.

## Completion

Record the input meaning, configuration choices, and promised projections.
Confirm the decomposition against the requested uses, then check the concrete
request through the proposed entry point. Keep unresolved input meaning explicit;
a rendered result alone does not establish correctness.
