# V2 regression threshold review

Reviewed on 2 August 2026 against the isolated local synthetic PostgreSQL 17
fixture. This is an engineering default for QueryPilot Local, not approval to
reuse the value against a production database.

## Evidence

- The pilot used the dedicated `querypilot_app` role in a read-only
  transaction with statement and lock timeouts.
- The two allowlisted queries were measured in two independent warm-cache
  runs with nine samples per query.
- Both runs recommended an execution-time ratio of `1.5`.
- The recommended global absolute deltas were `8.082 ms` and `15.405 ms`.
- Credentials, recommendations, and automatically applied thresholds were not
  recorded in either report.

The committed default rounds the more conservative observed delta upward:

- execution ratio: `1.5`;
- execution delta: `15.5 ms`;
- root-cost ratio: `1.25` (unchanged);
- an index-backed access path changing to a sequential scan remains an
  independent regression signal.

## Decision boundary

These defaults are accepted for the local synthetic fixture and CI evidence.
Any separately operated database must run its own calibration and receive its
owner or DBA approval before QueryPilot thresholds are treated as operational
policy. No production authorization is claimed by this review.
