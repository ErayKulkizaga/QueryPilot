# QueryPilot V2 plan baseline and regression contract

Status: first V2 slice implemented after the `v1.0.0` release.

## Goal

QueryPilot can preserve the plan produced by a reviewed analysis and compare a
later plan for the same normalized SQL. The feature identifies measurable plan
changes without converting those changes into an optimization recommendation.

## API

- `POST /api/v1/baselines` stores the plan attached to a non-expired
  `analysis_id`.
- `GET /api/v1/baselines?limit=50` lists local baselines.
- `POST /api/v1/baselines/{baseline_id}/comparisons` compares a baseline with a
  non-expired current `analysis_id`.

Baselines are persisted in a local SQLite database. The default path is
`data/querypilot_baselines.sqlite3`, which is excluded from Git.

Run a live same-query baseline comparison against the synthetic PostgreSQL
fixture:

```powershell
python -m scripts.baseline_smoke
```

## Comparison boundary

A comparison is rejected with HTTP 409 unless the normalized SQL fingerprints
match. QueryPilot does not substitute parameters, execute SQL captured from
`pg_stat_statements`, or compare unrelated statements.

The response contains:

- baseline and current execution time;
- baseline and current root cost;
- node-count change;
- added, removed, node-type-changed, and index-changed nodes;
- deterministic regression reasons; and
- `recommendations_generated=false`.

## Regression evidence

The default thresholds are:

- execution time at least 1.5 times the baseline and at least 1.0 ms slower;
- root cost at least 1.25 times the baseline; or
- an index-backed relation access path changing to a sequential scan.

Execution-time thresholds are deliberately conjunctive. A large percentage on
a sub-millisecond query is not enough without the absolute delta. Thresholds
can be changed through `QUERYPILOT_REGRESSION_*` environment settings.

## Safety properties

- Baseline creation reuses an already validated and executed analysis.
- Comparison never runs the stored SQL.
- Baseline SQL and plans remain local.
- Different normalized SQL is rejected.
- A regression alert is evidence, not a diagnosis of root cause.
- No LLM is involved.
- No recommendation or SQL change is produced.

## Next slice

The repository CI runs the complete release gate, including comparator,
baseline-store, API, and UI tests. The next product increments are:

1. Support explicit baseline deletion and retention policies.
2. Add repeated-sample aggregation so timing comparisons can use medians.
3. Link a workload-ranked query to representative SQL and a reviewed baseline.
4. Add checked-in named plan contracts for release-specific queries.
