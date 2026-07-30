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
- The public V2 showcase is synthetic and database-free; plan analysis remains
  browser-only, while an optional evidence-only request can produce a grounded
  cloud-AI explanation.
- The public AI path cannot run for no-answer results, never receives the full
  plan, selects its own category source, and falls back to the deterministic
  report when the model output is invalid or unavailable.
- The release gate passes 97 Python tests at 88.66% coverage, one real-browser
  Streamlit workflow, and 12 public behavior tests plus the rendered-shell
  check.
- Python and public dependency audits report zero known vulnerabilities.

## Remaining product boundaries

- The full V2 workflow remains a local engineering tool, not a hosted
  production database service.
- Authentication, encrypted connection management, multi-user ownership, and
  production workload authorization are not implemented.
- Query plan threshold calibration can now produce a sanitized review report,
  but a separately authorized non-production run and DBA approval remain
  required before promotion.
- Cold-cache labels record operator-controlled conditions; QueryPilot does not
  clear PostgreSQL or operating-system caches.
- Evidence-grounded Foundry Local generation remains outside the deterministic
  correctness path and is slow on CPU.
- Public Gemini usage depends on a third-party free-tier quota and processes
  only the sanitized evidence payload; privacy-sensitive plans should use the
  local Foundry path.

## Promotion rule

Promote the beta to `v2.0.0` only after the complete workflow is exercised
against a separately authorized non-production PostgreSQL database and its
thresholds are reviewed. No production credential or database belongs in the
public demo.
