---
name: dataframe-pipelines
description: Design or review dataframe-centric analysis components that preserve data meaning through computation. Use for semantic specifications and bindings, portable dataset meaning, validation scope and evidence, lazy execution, or diagrams of named computations.
---

# Dataframe pipelines

Own the meaning and computation principles for dataframe-based analysis in
business decisions and machine learning R&D. Stage: shaping, informed by empirical
prototypes. The aim is a semantic interface between modules, APIs, and data
artifacts: callers can understand what a dataset means and which operations fit
it. Validation is one use of this interface.

A dataframe-centric component is a specialized reusable analysis component.
[Analysis components](../analysis-components/SKILL.md) owns its public contract,
composition, reuse, and relationship with reports. This skill guides meaning
and computation inside the component, whether used by a report or another caller.
Build on the storage, interchange, and query engines agents already know.

```text
Meaning
├── specification: column roles, row meaning, grain, relationships, rules
├── binding: semantic roles → physical fields
├── computation: domain operations, metrics, features, dependencies
├── validation: evaluate requirements on their declared data scopes
└── observability: outcomes, violating data, lineage, inspection
```

## Specify meaning independently of representation

Describe column meaning in language humans and agents can read. Declare units
and accepted physical type ranges where computation depends on them. State what
one row represents, its grain and population, and applicable relationships and
rules. A physical schema alone cannot express these meanings.

Keep column and rule specifications usable independently of a dataset contract,
and contracts independently of bound data or checker execution. Adding feature
columns need not invalidate an existing contract unless it restricts extra fields.
A rule can concern a row, group, whole table, or relationship between datasets.
Row meaning is a declaration; rules check the properties that can be evaluated.

Bind semantic roles to source fields through explicit substitution. Matching
canonical names are the identity binding. Express reusable checks and domain
computations against those roles so source spelling can vary.

```text
meaning: event_time             event time, Unix epoch nanoseconds
accepted types: Int64 | UInt64  where the operation supports both
binding: event_time → ts        physical field: ts, UInt64
```

Binding supplies the field for a role; it does not convert units, rename data,
or prove its origin or values. Keep the binding available for inspection.
Reject or resolve ambiguous input meaning before relying on it.

## Preserve meaning through computation and transport

Carry definitions, populations, grain, and time assumptions through metrics,
features, and domain operations. State each operation's input and output meaning;
outputs can have a different contract. A filter changes the population, and a
join can change grain even when the physical columns look familiar.

Check relationships between inputs and outputs when the promised computation
depends on them. For example, uniqueness of one row per order does not establish
that it is the first observed event. That claim needs evidence about selection
from the input. Numerically correct calculations can still answer the wrong question.

Make persisted or transported datasets understandable without the producing
framework. Carry their meaning, bindings, and relevant provenance with them in
readable metadata or an associated artifact. Update these descriptions when
transformations change meaning. Serialized declarations communicate intent;
they neither prove validity nor necessarily contain executable checkers.

## Keep specifications, evaluation, and evidence distinct

A specification states a requirement. Evaluation checks it on a particular data
scope. Evidence records the outcome; acceptance policy decides the response.
Keep data violations separate from execution errors and missing checkers. A
required rule without an evaluator must not silently pass on a checked path.
Checking and binding do not silently repair or coerce data.

Provide structured diagnostic evidence, not just a Boolean: the rule, evaluated
scope, counts, and violating rows or groups with relevant values. Derive summaries
and detailed inspection from the same result. Bounded diagnostic samples must not
stand in for full-scope counts. Keep evidence tied to the data realization checked;
if inspection rereads a source, make its stability requirement explicit.

Checks establish only the evaluated properties. Consistent metrics and validated
data do not establish business value or causality. Human intent and taste still
guide questions and decisions. Presentation supports comparison and investigation
while preserving the underlying meaning.

## Preserve validation scope and agreed guarantees

Attach requirements to meaningful input and output boundaries, not every native
transformation. Retain required validation of the original input scopes. A filter,
aggregation, join, or new result must not erase an obligation merely because the
affected rows are no longer visible downstream.

Favor lazy evaluation and minimal computation and materialization. Validation
timing and execution strategy are optimization choices. Preserve correctness,
validation scope, and required release guarantees when changing either. A checked
release may compute before checks finish, but must meet its promised acceptance
policy before releasing the result. Keep explicit diagnostic checking available.

State which public paths provide these guarantees. Native engine access can be
an intentional escape; it must not imply checked results. Do not expand an agreed
API guarantee into an attempt to guard every possible use of the underlying data.

## Show named computations and their connections

Derive pipeline diagrams from actual named computation calls and their dataset
connections, without separately authored diagram wiring. Signatures describe
possible inputs and outputs; calls identify the actual dependencies, including
distinct uses of the same function with different parameters.

Group important steps into input adapters, domain computations, and outputs.
Multiple domain steps can form a DAG; split large workflows into smaller pipelines.
Show retained check scopes as an optional view of those same stages. Adding a
visible step does not itself create a validation boundary.

Keep native plans and execution evidence in separate inspection views, with
explicit drill-downs when useful. Deriving the diagram must not execute data
transformations or checks. It explains composition without requiring a DAG
executor, scheduling system, or capture of every native expression.

## Keep implementation choices open

These principles select neither a language nor a dataframe wrapper. Investigate
how dataset contracts, validation plans, and metric or feature definitions compose;
do not assume one universal object or module. Compare existing tools against the
needed properties and integration cost before choosing custom machinery.

Authoring syntax, serialization, visualization, and evaluation can serve the same
semantic model. Choose their representation around required uses and preserve
meaning between them; a fluent API, class model, or DSL is not a goal by itself.
Each prototype owns its concrete choices and evidence. As choices stabilize,
move enforceable rules into types and APIs; retain intent and rationale here.

## Apply and check the principles

Start from the caller's use: identify input meaning and bindings, intended
transformations, output meaning, and required validation scopes. Trace those
through one concrete journey, including inspection and transport where relevant.
When reviewing a change, inspect evidence for the promised computation and release
outcomes. A declaration or diagram alone cannot establish correctness.
