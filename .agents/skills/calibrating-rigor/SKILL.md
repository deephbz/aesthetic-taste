---
name: calibrating-rigor
description: Calibrate component rigor and integration with the user when balancing iteration with shared use, reviewing mixed experimental and maintained code, or considering promotion into shared APIs.
---

# Calibrating rigor

Help the user decide which commitments each component needs now. Use this
vocabulary and discussion workflow during research, development, debugging,
experiment review, or PR preparation when those commitments are in question.
The invocation sets the task and desired result; extraction, refactoring,
promotion, and publication are possible outcomes, not required stages.
Stage: shaping. Status: draft for use and refinement with the user.

This skill owns architectural calibration. Work OS remains the authority for
source bundles, fluid allocation between prose and code, artifact placement,
and change composition. Use its relevant references when those decisions arise.
Implementation conventions and detailed naming guidance belong to their existing
sources. Here, decide which obligations justify that work for each component.

## Terminology

- **Consumer:** code, a person, or an agent that relies on a component's behavior
  or output. Distinguish code consumers from people using a result to decide.
- **Contract:** the meaning and observable guarantees a consumer can rely on,
  including assumptions, input requirements, invariants, outputs, and failures.
- **Rigor:** the precision and verification needed for the component's current
  responsibility. Correctness evidence and interface stability are separate concerns.
- **Stability:** a commitment to preserve agreed behavior for identified consumers.
  It does not mean the research question or implementation has stopped changing.
- **Coupling:** dependence that makes a change in one component affect another.
  Imports, schemas, configuration, execution order, and shared state can all couple work.
- **Isolation:** limiting those effects through explicit boundaries and ownership.
  A separate directory alone does not establish isolation.
- **Promotion:** deliberately increasing a component's shared role and obligations.
  Moving files is neither necessary nor sufficient for promotion.

Experimental and mature components can coexist in one versioned repository.
Versioning preserves source; it does not promise a stable API. Calibrate individual
components and surfaces, rather than assigning one quality level to the repository.
Review and merge criteria follow those obligations. Experimental work can be ready
to merge while its API remains provisional and its integration remains limited.

## Interactive workflow

Use the portions needed for the invocation. Carry forward decisions the user has
already made; focus questions on unresolved choices that change the next action.

### Establish the current structure

Inspect the named code and local state before recommending boundaries. Identify
responsibilities, entry points, actual consumers, data sources, transformations,
outputs, and shared state. Include pending changes that overlap the proposed work.
Distinguish observed connections from assumptions and proposed connections.

Show a compact architecture and data-flow sketch at one consistent level of
detail. Label edge meanings so data flow and code dependence are distinguishable.
Include important crossings into storage, runtime configuration, or other projects
when they affect the decision. The map is sufficient when each candidate's role,
consumers, and effects on neighboring work can be explained; mark remaining unknowns.

### Discuss obligations component by component

Use the decision guide below to propose priorities and explain their costs. Ask
the user to resolve material choices not settled by the invocation or prior context.
Discuss alternatives using the actual code: what becomes easier to change, what
becomes a promise, who benefits, and which work must change with it.

For each component under consideration, establish the current emphasis: correctness,
contract precision, compatibility, extensibility, performance, iteration speed,
or integration. These can differ within one component. A critical experiment can
need strong result checks while retaining a provisional API.

This discussion is sufficient when the user has a concrete proposed boundary and
can see the obligations, costs, and unresolved decisions. Keep unresolved choices
visible; do not convert agent recommendations into accepted commitments.

### Choose a bounded next action

Depending on the user's task, the next action may preserve isolation, tighten one
contract, change a data boundary, promote a capability, prepare a PR, or continue
exploration. Describe the specific change and the evidence needed to assess it.
Apply existing authorization; a discussion alone does not authorize unrelated cleanup.

When implementing, verify both the changed boundary and its actual use. When only
discussing, a grounded decision or clearly stated open choice is a valid result.
Completion follows the invoked task, not a universal shipment checklist.

Record accepted decisions in the existing local design or working-context home:
responsibility, consumers, current commitments, accepted uncertainty, and the next
condition that would justify revisiting them. Keep historical observations separate.

## Decision guide

| Consideration | Question and rule of thumb |
|---|---|
| Correctness | What fails if this result is wrong? Match evidence to that consequence, even with no code consumers. |
| Contract precision | What must consumers understand to use this safely? Make shared meaning and input invariants explicit. |
| Compatibility | Who relies on current behavior? Protect accepted commitments and coordinate meaningful changes with those consumers. |
| Extensibility | Which concrete variation must be possible next? Preserve that freedom without inventing a general framework. |
| Iteration speed | Which definitions or methods are still changing? Keep their revision local and inexpensive. |
| Performance | Which measured cost limits useful work? Improve that path when the benefit warrants the added complexity. |
| Integration | What dependencies and shared effects will this introduce? Keep provisional work easy to change independently. |

Actual reuse and credible planned consumers justify more contract investment than
speculative reuse. Consumer count is a signal, not a score: one critical decision
can justify stronger correctness evidence than many low-consequence uses.

Three common patterns illustrate the guide; they are not mandatory maturity tiers:

- **Shared definition**, such as a business metric expressed in Polars: prioritize
  meaning, assumptions, input invariants, and evidence for the computed result.
  Small implementations can carry large downstream obligations.
- **Reusable analysis component:** prioritize a small, clear contract and checks
  at the boundary consumers use. Internal freedom is valuable while that contract holds.
- **Outermost orchestration**, such as a report or experiment driver: prioritize
  clear intent and evidence from real runs, rendered output, or integration checks.
  Thin wiring usually needs little API commitment or unit-test machinery. Substantial
  domain logic and externally consumed outputs still carry their own obligations.

In this repository, the [report model](../../../docs/report-model.md) separates
generic tooling, reusable analysis components, and report orchestration. Those
layers assign responsibilities; they do not prescribe fixed rigor levels.

## Isolation before deeper integration

The less settled a component's contract and discipline, the less intrusive its
integration should be. Keep it locally owned and independently changeable while
preserving enough source and evidence for continued work.

An example, script, or tool directory can provide that home. Inspect imports,
dependency installation, configuration, startup hooks, output locations, and writes
to shared state. Prefer provisional code consuming established public surfaces;
making maintained code depend on experimental internals creates new commitments.
Reuse established facilities where appropriate; isolation does not require copying
them or building a separate stack.

Before deeper integration, identify the new consumers, the contract they need,
and evidence that the boundary works. Then choose the smallest useful promotion
with the user. A new consumer, repeated coordinated edits, or a changed consequence
of error can justify revisiting the decision. Remaining isolated is also a valid
long-term outcome.
