# QueryPilot V2 portfolio closeout

Status: feature-complete in `v2.0.0` and finalized for portfolio presentation
in `v2.0.1` on 7 August 2026.

## What the release proves

QueryPilot connects three deterministic evidence stages:

1. rank eligible PostgreSQL statements by measured total execution time;
2. require reviewed representative SQL before plan analysis; and
3. compare a later same-query plan with a measurement-compatible baseline.

The workflow does not execute SQL captured from `pg_stat_statements`, invent
parameter values, apply an index, or turn workload statistics into an
optimization recommendation.

## Acceptance evidence

- A least-privilege workload projection hides direct `pg_stat_statements`
  access from the application role.
- PostgreSQL `$1` and `$2` placeholders are blocked until reviewed
  representative values are supplied.
- Cold-cache, warm-cache, and uncontrolled samples cannot be compared across
  groups.
- Baseline imports require strict bounded JSON, read-only SQL, and a matching
  query fingerprint; imported SQL is never executed.
- Named plan contracts protect the missing-index and healthy primary-key
  fixture behavior in CI.
- The guarded pilot requires an exact database-name match, a non-privileged
  read-only role, an explicit query allowlist, and a second opt-in before
  `EXPLAIN ANALYZE` execution.
- An isolated PostgreSQL 17 fixture was verified with two independent
  nine-sample warm-cache runs. The reviewed local defaults are a `1.5`
  execution ratio and `15.5 ms` absolute delta.
- The public showcase is database-free and keeps complete plans in the
  browser. Its optional AI request sends only bounded evidence and a
  category-owned PostgreSQL knowledge chunk.
- Unknown evidence, citations, numbers, URLs, identifiers, HTML, SQL actions,
  and malformed model output are rejected.
- The release gate passes 103 Python tests at 88.68% coverage, one real-browser
  Streamlit workflow, and 19 public behavior, integration, and rendered-shell
  tests.
- Python and public dependency audits report zero known vulnerabilities.

## Deliberate scope boundaries

QueryPilot is a local engineering and portfolio project, not a commercial
hosted database service. Public account management, encrypted customer
connection storage, multi-user tenancy, billing, and production workload
authorization are intentionally out of scope. Their absence is not an
unfinished release requirement.

Cold-cache labels record operator-controlled conditions; QueryPilot does not
clear PostgreSQL or operating-system caches. Foundry Local enrichment remains
outside the deterministic correctness path and can be slow on CPU. Public
Gemini usage depends on a third-party free-tier quota and receives only the
sanitized evidence payload.

No production credential or database belongs in the public demo. Any use
against a separately operated database still requires its owner or DBA to
approve the queries and environment-specific thresholds.

## Completion decision

`v2.0.1` is complete and frozen for portfolio use. New product capabilities
would belong to a separately scoped future project or version; they are not
required to present, evaluate, or reproduce this release.
