---
document_id: pg-indexes-01
title: PostgreSQL Indexes and Selective Predicates
source_url: https://www.postgresql.org/docs/current/indexes.html
---

# PostgreSQL Indexes and Selective Predicates

## When a sequential scan is reasonable

A sequential scan is not automatically bad. Reading most of a small table can
be faster than traversing an index and fetching scattered heap pages. The
planner may also prefer a sequential scan when a predicate returns a large
fraction of the table. Diagnosis should therefore combine relation size,
returned rows, rows removed by the filter, buffer activity, and execution time.
QueryPilot reports a potential missing index only when the filter appears
selective and the scan examines enough rows to provide meaningful evidence.

## Selective predicates

An index is most useful when its leading key can rapidly narrow the candidate
set. Equality predicates on high-cardinality columns, such as a unique email
address, are common examples. Range predicates can also benefit, depending on
data distribution and ordering. A plan that scans 25,000 rows to return one
row provides stronger index evidence than a plan that returns 20,000 of those
rows. The recommendation must name the observed predicate and remain a review
item rather than an automatically applied change.

## Index costs and trade-offs

Indexes consume disk space and add work to inserts, updates, deletes, vacuum,
and backup operations. Redundant indexes can hurt write-heavy workloads even
when they improve one read query. Before creating an index, review existing
indexes, query frequency, write frequency, column width, and expected
selectivity. Measure the query plan before and after the proposed change on a
representative dataset. QueryPilot only displays recommendation SQL; it never
executes index creation.

## Index-only and bitmap access

PostgreSQL has several index-related plan nodes. An `Index Scan` uses index
entries to locate heap tuples. An `Index Only Scan` may avoid heap access when
the required columns are present in the index and visibility information allows
it. A `Bitmap Index Scan` can collect many tuple locations and a `Bitmap Heap
Scan` can visit heap pages efficiently. These alternatives mean the correct
goal is not “replace every sequential scan,” but “reduce total work for the
observed access pattern.”

