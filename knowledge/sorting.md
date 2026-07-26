---
document_id: pg-sorting-01
title: PostgreSQL Sorting and Temporary Disk Use
source_url: https://www.postgresql.org/docs/current/runtime-config-resource.html
---

# PostgreSQL Sorting and Temporary Disk Use

## Reading sort evidence

An analyzed sort node can include `Sort Method`, `Sort Space Used`, and `Sort
Space Type`. Values such as `external merge` or a space type of `Disk` show
that the operation used temporary storage instead of remaining entirely in
memory. Temporary read and written block counts provide additional spill
evidence. A disk sort may be acceptable for an infrequent reporting query, but
it deserves attention when latency, concurrency, or temporary I/O is material.

## Reduce rows before sorting

The safest optimization is often to reduce the input before it reaches the sort.
Selective filters, better join order, pre-aggregation, or an appropriate limit
can reduce both memory and comparison work. Review whether predicates are being
applied as early as possible and whether upstream row estimates match reality.
A large unexpected sort can be a downstream symptom of cardinality
misestimation rather than an isolated memory problem.

## Ordered index access

A B-tree index can sometimes deliver rows in the order required by `ORDER BY`,
avoiding an explicit sort. This is most useful when the index also supports
selective filtering or a small `LIMIT`. Scanning a large index only to avoid a
sort may be slower than a sequential scan followed by sorting. Column order,
sort direction, null ordering, filtering predicates, and the number of returned
rows all affect whether an index provides a useful ordering.

## Treat work_mem carefully

`work_mem` is a per-operation allowance, not a single global query budget. One
query can run multiple sorts or hashes, and many concurrent sessions can each
consume memory. Increasing it globally based on one plan can create system-wide
memory pressure. Prefer reducing work and reviewing indexes first. If tuning is
justified, test a session-level value for the representative workload and
measure spill behavior, latency, and concurrent memory risk.

