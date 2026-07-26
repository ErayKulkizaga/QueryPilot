---
document_id: pg-multicolumn-01
title: PostgreSQL Multicolumn Index Design
source_url: https://www.postgresql.org/docs/current/indexes-multicolumn.html
---

# PostgreSQL Multicolumn Index Design

## Leading columns matter

For a multicolumn B-tree index, constraints on the leading columns usually
determine how narrowly PostgreSQL can scan the index. Equality constraints on
leading columns followed by an inequality on the next column form a common
effective pattern. Later columns may still be checked in the index and can
reduce heap visits, but they do not always reduce the portion of the index that
must be scanned. Index column order should follow observed query predicates,
not alphabetical order.

## Filter and ordering together

A multicolumn index can sometimes support both filtering and ordering. For
example, an equality filter on `customer_id` followed by an order on
`created_at` can motivate an index on `(customer_id, created_at)`. Direction and
null ordering must match the query's needs, and the expected result count still
matters. The design should be tested with the actual `WHERE`, `ORDER BY`, and
`LIMIT` combination rather than inferred from column names alone.

## Avoid redundant combinations

Adding every observed column combination creates storage and write overhead.
Before proposing a new composite index, inspect existing primary, unique, and
secondary indexes. An existing index may already provide the needed leading
prefix, while another may become redundant after the change. Consolidation is
workload-specific: an index useful for one ordering may not replace another
index used by a different selective predicate.

## Included columns and coverage

PostgreSQL supports included non-key columns that can help an index-only scan
cover a query without changing the index search key. Included columns increase
index size and write cost, and index-only scans also depend on heap-page
visibility. Coverage should therefore be considered after the selective key and
ordering requirements are correct. QueryPilot can explain this trade-off, but
should not generate a covering-index recommendation without schema and workload
context.

