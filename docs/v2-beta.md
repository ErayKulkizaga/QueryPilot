# QueryPilot V2 beta acceptance

Status: `v2.0.0-beta.3` public-AI release candidate.

## What the beta proves

QueryPilot now connects three deterministic evidence stages:

1. rank eligible PostgreSQL statements by measured total execution time;
2. require reviewed representative SQL before plan analysis; and
3. compare a later same-query plan with a measurement-compatible baseline.

The workflow does not execute SQL captured from `pg_stat_statements`, invent
parameter values, apply an index, or turn workload statistics into an
optimization recommendation.

## Acceptance evidence

- A least-privilege workload projection hides direct `pg_stat_statements`
  access from the application role.
- PostgreSQL `$1`/`$2` placeholders are blocked at the workload handoff until
  representative literal values are supplied.
- Cold-cache, warm-cache, and uncontrolled samples cannot be compared across
  groups.
- Baseline imports require strict bounded JSON, read-only SQL, and a matching
  query fingerprint; imported SQL is never executed.
- Named live plan contracts protect the missing-index and healthy primary-key
  fixture behavior in CI.
- A guarded pilot runner requires an exact database-name match, a non-privileged
  read-only role, an explicit query allowlist, and a second opt-in before
  `EXPLAIN ANALYZE` execution.
- The committed synthetic pilot smoke measured two allowlisted queries without
  recording credentials, applying thresholds, or generating recommendations.
- A fresh isolated PostgreSQL 17 fixture was re-verified on 2 August 2026 with
  two independent nine-sample warm-cache runs. The reviewed local defaults are
  a `1.5` execution ratio and `15.5 ms` absolute delta; the review explicitly
  does not claim production DBA approval.
- The public V2 showcase is synthetic and database-free; plan analysis remains
  browser-only, while an optional evidence-only request can produce a grounded
  cloud-AI explanation.
- The public AI path cannot run for no-answer results, never receives the full
  plan, selects its own category source, and falls back to the deterministic
  report when the model output is invalid or unavailable.
- The release gate passes 103 Python tests at 88.68% coverage, one real-browser
  Streamlit workflow, and 19 public behavior, integration, and rendered-shell
  tests.
- Python and public dependency audits report zero known vulnerabilities.

## Remaining product boundaries

- The full V2 workflow remains a local engineering tool, not a hosted
  production database service.
- Authentication, encrypted connection management, multi-user ownership, and
  production workload authorization are not implemented.
- Query plan threshold calibration now has a sanitized local review report.
  A target owner or DBA must still approve separately calibrated values before
  any non-local database treats them as operational policy.
- Cold-cache labels record operator-controlled conditions; QueryPilot does not
  clear PostgreSQL or operating-system caches.
- Evidence-grounded Foundry Local generation remains outside the deterministic
  correctness path and is slow on CPU.
- Public Gemini usage depends on a third-party free-tier quota and processes
  only the sanitized evidence payload; privacy-sensitive plans should use the
  local Foundry path.

## Promotion rule

Promote the beta to `v2.0.0` only after a target owner or DBA reviews the
calibration for the intended non-local environment. The isolated local
PostgreSQL workflow and engineering threshold review are complete, but they do
not grant production authorization. No production credential or database
belongs in the public demo.
