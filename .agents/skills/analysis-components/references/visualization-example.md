# Shaping a visualization component

This example illustrates the [component design procedure](../SKILL.md#shape-reuse-from-a-concrete-request).
Its geometry and configuration choices belong to this use case, not every
analysis component.

A request might be: show the number of resting orders at each price level,
with price on the y axis and time on the x axis. Use one horizontal element per
level, colored by order count. Likely variations might color by notional,
change element height, or add a second book.

Decompose that request into a per-level geometry, a scalar-to-color mapping,
and a payload for each price level and timestamp. The payload supplies order
count for the first request and other measures for supported variations.

The semantic input model names book levels as its dataset role and one row per
level per timestamp as its grain. Its field roles include price, time, and
measures. Keep the geometry fixed for this component; make the measure used by
the style mapping configurable. Other components can make different boundaries.

Color map, element height, measure selection, and axis ranges are candidate
controls. Confirm which variations the requester needs before exposing them.
The first request should be satisfied by configuring that component, rather
than by maintaining a separate implementation for each measure.

Keep the report's wiring and layout local enough that changing one intended
view choice requires one edit and rerun.
