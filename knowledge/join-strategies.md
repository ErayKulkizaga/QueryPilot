---
document_id: pg-joins-01
title: PostgreSQL Join Strategies
source_url: https://www.postgresql.org/docs/current/planner-optimizer.html
---

# PostgreSQL Join Strategies

## Nested loop behavior

A nested loop takes rows from its outer child and executes the inner child for
each relevant outer row. This is often excellent when the outer input is small
and the inner input has a selective index lookup. It becomes expensive when the
outer side produces many rows or the inner side lacks an efficient access path.
The clearest evidence is a high `Actual Loops` value on the inner node combined
with meaningful total time or buffer work.

## Hash join behavior

A hash join builds an in-memory hash table from one input and probes it with
rows from the other input. It is commonly effective for equality joins with
larger inputs. Hash joins can become less attractive when the build input is
larger than estimated or when memory pressure causes batching and temporary
I/O. The presence of a hash join is not itself a diagnosis. Review build rows,
batch count, memory use, temporary blocks, and the accuracy of row estimates.

## Merge join behavior

A merge join consumes both inputs in join-key order. It can be efficient for
large, ordered datasets and can exploit existing index order. If the inputs are
not already ordered, PostgreSQL may add sort nodes whose cost becomes part of
the join strategy. Review those sorts for disk spill and confirm whether the
required ordering can be supplied more cheaply. Merge joins are especially
relevant for equality and range-compatible join conditions.

## Diagnose causes, not join names

Disabling a join algorithm is rarely a durable fix. An apparently expensive
nested loop may be caused by missing indexes, inaccurate statistics, skewed
data, or a predicate that returns far more rows than expected. A hash join may
spill because its build side was underestimated. A merge join may inherit an
expensive sort. QueryPilot reports the observed loop and timing evidence, then
recommends checking join keys, selectivity, and statistics instead of forcing
a planner setting.

