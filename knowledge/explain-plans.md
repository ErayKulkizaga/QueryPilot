---
document_id: pg-explain-01
title: Reading PostgreSQL EXPLAIN Plans
source_url: https://www.postgresql.org/docs/current/using-explain.html
---

# Reading PostgreSQL EXPLAIN Plans

## Plans are trees, not flat lists

A PostgreSQL execution plan is a tree of plan nodes. Leaf nodes obtain rows
from tables, indexes, values, or functions. Parent nodes consume their child
rows to join, sort, aggregate, limit, or otherwise transform the result.
Interpret a node together with its children and its loop count. A cheap inner
node can dominate total work when a nested loop executes it thousands of times.
Machine-readable JSON preserves this hierarchy and should be traversed
recursively. Text indentation is useful for people, but it is a fragile input
format for software.

## Estimated cost and estimated rows

`Startup Cost`, `Total Cost`, and `Plan Rows` are planner estimates, not measured
milliseconds or guaranteed row counts. Cost units combine configurable
assumptions about CPU and I/O. They are primarily useful for comparing
alternative plans considered by the same PostgreSQL instance. Estimated rows
are especially important because they influence join order, join algorithm,
aggregation strategy, and whether an index appears worthwhile. A high cost is
not proof of a problem by itself; compare it with actual work and the intended
workload.

## Actual rows, time, and loops

`EXPLAIN ANALYZE` executes the statement and adds measured values such as
`Actual Rows`, `Actual Total Time`, and `Actual Loops`. For a node executed more
than once, actual row and time values are averages per loop in PostgreSQL plan
output. Total work therefore depends on both the per-loop values and the loop
count. QueryPilot uses these measurements only on its synthetic local database.
It does not run `ANALYZE` against an arbitrary production database because the
query is really executed.

## Buffers and rows removed

`BUFFERS` reports shared, local, and temporary block activity. Shared hits mean
the requested block was already available in the PostgreSQL buffer cache;
shared reads required a physical read into that cache. Temporary blocks often
signal spill activity from sorts, hashes, or materialization. `Rows Removed by
Filter` shows how many candidate rows a filter rejected. A large number can
support a selective-access diagnosis, but must be interpreted with table size,
returned rows, query frequency, and write cost before recommending an index.

