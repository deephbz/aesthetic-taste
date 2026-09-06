---
name: table-presentation
description: Design or review report tables for accurate comparison and lookup. Use for table structure, numeric formatting, visual emphasis, or choosing Great Tables versus pandas Styler.
---

# Table presentation

Help report authors make tables that support accurate comparison and lookup.
This skill owns table anatomy, layout, value formatting, visual emphasis, and
renderer selection. Metric definitions, data validation, report deployment, and
a shared table library remain outside its scope.

Stage: shaping. The guidance remains proposed for review; renderer advice is
not a package contract.

A presentation table is data visualization for human readers. Choose its
structure from the reader's question, then format values and apply styles.
Great Tables' distinction between data tables and display tables motivates this
approach ([introduction](https://posit-dev.github.io/great-tables/)).

For this repository, the [report contract](../../../docs/report-contract.md)
owns data authority and host parity; [report presentation](../report-presentation/SKILL.md)
owns embedding.

## Apply the guidance

1. Identify the reader's question, row meaning, comparison, and target outputs.
2. Apply the structure, formatting, and emphasis guidance below to the source data.
3. When choosing or using Great Tables or pandas Styler, read
   [renderer guidance](references/renderers.md) for ownership, API mapping, and examples.
4. Verify displayed values against the analytical result and inspect each requested output.
   Report which outputs passed inspection and which remain unverified.

## Structure the comparison

State what one row represents and what the reader must compare. Use tables for
exact values, mixed measures, or lookup; use charts when shape or trend dominates.
Order rows by time, rank, or a stable domain order. State filters and top-N limits.
Keep omitted results available as data when follow-up questions need them.

Put row identity first and related measures together. Place baseline, candidate,
and difference side by side. Replace storage names and unexplained indexes with
plain-language labels. Give a standalone table a clear title; an adjacent caption
can serve that role in a report. Add scope in a subtitle when needed.

```text
Title / subtitle              Question or finding; population, period, filters
                 Spanner      Shared meaning, e.g. Revenue above 2023 and 2024
Stub heading     Column labels and units
Row group                     Category shared by the following rows
Row label        Values       One observation or result
Summary label    Values       Explicit subtotal or aggregate
Footnotes                     Definitions, methods, local exceptions
Source note                   Origin, version/date, link to evidence
```

Use row groups for real categories and spanners to remove repeated labels.
Prefer shallow hierarchy. Separate totals with a label and space or a rule.
Identify weights and denominators; an average of rates is not necessarily a
pooled rate. Keep essential definitions visible and attach local exceptions to
the affected cells. Source notes must lead back to evidence.

## Format meaning, not storage

Keep values numeric until rendering. Compute differences, ranks, intervals, and
summaries upstream. Never use formatted strings as analytical inputs.

Choose precision from uncertainty and the decision scale, not a fixed decimal
count. Keep precision consistent within comparable measures. Add digits or show
a difference when rounding would hide it. Distinguish a small nonzero value from
zero, for example with “<0.1”.

State units, currency, scaling, and time zone where relevant. Use scientific
notation or K/M abbreviations when they help this audience; define the scale.
Keep dates, separators, and text conventions consistent. Preserve leading zeros
in identifiers. A proportion of 0.123 is 12.3%; a rise from 10% to 12% is
+2 percentage points.

Distinguish zero, unavailable, not applicable, and suppressed values. Define
missing markers and retain distinct reasons in data. Keep uncertainty beside
its estimate and state interval type and level. Color or stars cannot replace
that information.

## Make scanning easy

Left-align labels; right-align comparable numbers and headings. Align decimal
points when mixed precision needs it. Use tabular numerals where supported.
Center short categorical marks only when useful; numeric identifiers need not
look like measurements.

Give labels enough width and wrap before reducing font size. Keep values and
units together. Prefer whitespace and light horizontal rules to boxed cells.
Use row striping only when readers need help tracking long rows. At narrow
widths, split meaningful sections or use local horizontal scrolling. Keep the
title, row identity, and notes available; do not shrink text until it is unreadable.

## Make emphasis and small visuals earn their place

Start neutral. Use subtle fills to separate column groups or row categories
when spacing is insufficient. Keep these category cues distinct from quantitative
color scales. Use an accent, weight, or target-row fill for the main comparison.
Negative does not mean bad; the measure defines favorable outcomes.

Use sequential color for magnitude and diverging color around a meaningful
reference. State the scale and keep its domain fixed across comparable views.
Scale each column separately only when each is an independent comparison.
Keep values readable and pair status color with labels or symbols and a key.

Use in-cell bars for magnitude and sparklines for trends. State the time window,
direction, and baseline; share scales when comparing magnitude across rows.
Independently scaled sparklines compare shape, not size. Preserve gaps in missing
data and keep exact values available. Small charts must answer a question that
numbers alone make hard to answer.

Use logos, icons, or badges only when recognition helps readers scan. Keep a
text label or accessible equivalent, use consistent sizing, and omit decoration.

## Reproduce and verify the result

Generate tables from versioned data references, code, and presentation settings.
Apply corrections to those sources, then regenerate; do not hand-edit final cells.
The table is a derived view, not a second source of truth.

Check displayed percentages, missing values, aggregates, and unit conversions
against the analytical result. Inspect actual notebook and served HTML for
clipping, broken groups, missing notes, contrast, and CSS leaks. Check long labels,
large values, and narrow widths. Verify requested print or spreadsheet outputs
separately through the [host verification procedure](../report-delivery/SKILL.md#verify-hosts-and-outputs).

Use real headers and check their associations in complex tables. Color, hover,
and position must not be the only ways to recover meaning. Retain accessibility
and correctness checks when simplifying the implementation.

