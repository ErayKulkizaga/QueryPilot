---
document_id: pg-statistics-01
title: PostgreSQL Planner Statistics and Cardinality
source_url: https://www.postgresql.org/docs/current/planner-stats.html
---

# PostgreSQL Planner Statistics and Cardinality

## Why cardinality estimates matter

PostgreSQL estimates how many rows each plan node will return. Those estimates
influence join order, join algorithm, scan choice, aggregation, and memory
expectations. QueryPilot compares `Plan Rows` with `Actual Rows` and treats a
tenfold difference as an initial signal, not an automatic root-cause verdict.
The most important misestimate is often the earliest node where estimates
diverge, because downstream nodes inherit that error.

## Refreshing table statistics

`ANALYZE` samples table data and updates statistics used by the planner.
Autovacuum normally performs this work, but bulk loads, rapid changes, or a
disabled autovacuum configuration can leave statistics stale. When estimates
are materially wrong, first confirm when the table was analyzed and whether the
current data distribution is representative. Re-running `ANALYZE` is a
diagnostic step, not a guarantee that every correlated predicate will become
accurate.

## Statistics targets and skew

The statistics target controls the amount of detail collected for a column.
Increasing it can improve estimates for skewed values or complex
distributions, at the cost of more planning statistics, analysis work, and
possibly planning time. Inspect common-value and histogram behavior before
raising the target. A blanket maximum target for every column is not a
responsible default. Focus on columns whose estimation errors alter important
plans.

## Extended statistics

Single-column statistics cannot fully describe relationships between columns.
When predicates combine correlated columns, PostgreSQL may multiply independent
selectivities and produce a large error. Extended statistics can capture
dependencies, multivariate distinct counts, or common value combinations for
selected column groups. They are appropriate when plan evidence and domain
knowledge show cross-column correlation. They still require `ANALYZE` and
should be evaluated with representative queries.

