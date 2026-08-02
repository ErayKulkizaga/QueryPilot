# QueryPilot V2 plan baseline and regression contract

Status: implemented in the `v2.0.0-beta.1` evidence workflow beta.

## Goal

QueryPilot can preserve the plan produced by a reviewed analysis and compare a
later plan for the same normalized SQL. The feature identifies measurable plan
changes without converting those changes into an optimization recommendation.

## API

- `POST /api/v1/baselines` aggregates one to nine plans attached to non-expired
  `analysis_ids`.
- `GET /api/v1/baselines?limit=50` lists local baselines.
- `POST /api/v1/baselines/{baseline_id}/comparisons` compares a baseline with a
  one-to-nine-sample current plan aggregate.
- `DELETE /api/v1/baselines/{baseline_id}` explicitly removes one baseline.
- `GET /api/v1/baselines/{baseline_id}/export` returns a strict portable JSON
  record.
- `POST /api/v1/baselines/imports` validates and stores a portable record under
  a new local ID.
- `GET /api/v1/baselines/{baseline_id}/report` returns a shareable Markdown
  evidence report.

Baselines are persisted in a local SQLite database. The default path is
`data/querypilot_baselines.sqlite3`, which is excluded from Git.
The newest 100 baselines are retained by default; the limit is configurable
through `QUERYPILOT_BASELINE_MAX_ITEMS`.

Every baseline is labeled `cold_cache`, `warm_cache`, or `unspecified`.
Comparison rejects different labels. QueryPilot does not clear PostgreSQL or
operating-system caches itself; the label records a measurement condition that
the operator explicitly controlled. This prevents a first disk-heavy run from
being silently compared with repeated in-memory runs.

Run a live same-query baseline comparison against the synthetic PostgreSQL
fixture:

```powershell
python -m scripts.baseline_smoke
```

## Comparison boundary

A comparison is rejected with HTTP 409 unless the normalized SQL fingerprints
match. QueryPilot does not substitute parameters, execute SQL captured from
`pg_stat_statements`, or compare unrelated statements.

Samples are aggregated with the median, the middle value after sorting the
measurements. Every sample must also have the same node path, node type,
relation, and index identity. Different plan structures are rejected rather
than averaged together.

The response contains:

- baseline and current execution time;
- baseline and current root cost;
- node-count change;
- added, removed, node-type-changed, and index-changed nodes;
- deterministic regression reasons; and
- `recommendations_generated=false`.

## Regression evidence

The default thresholds are:

- execution time at least 1.5 times the baseline and at least 15.5 ms slower;
- root cost at least 1.25 times the baseline; or
- an index-backed relation access path changing to a sequential scan.

Execution-time thresholds are deliberately conjunctive. A large percentage on
a sub-millisecond query is not enough without the absolute delta. The 15.5 ms
default is the conservative rounded maximum from two authorized nine-sample
warm-cache runs on the local synthetic fixture. It is not a production DBA
approval. Thresholds can be changed through `QUERYPILOT_REGRESSION_*`
environment settings after environment-specific review.

## Safety properties

- Baseline creation reuses an already validated and executed analysis.
- Comparison never runs the stored SQL.
- Baseline SQL and plans remain local.
- Different normalized SQL is rejected.
- Structurally different samples are rejected.
- Deletion requires an explicit baseline ID and user action.
- A regression alert is evidence, not a diagnosis of root cause.
- No LLM is involved.
- No recommendation or SQL change is produced.

## Completed V2 beta increment

The repository CI runs the complete release gate, including median aggregation,
retention, deletion, comparator, API, UI, and checked-in live plan-contract
checks. A plan contract names a release-specific query and its required or
forbidden access paths. CI fails if the fresh PostgreSQL fixture no longer
matches that reviewed behavior.

Portable imports are bounded to one read-only SQL statement, a matching
SHA-256 query fingerprint, one to 500 strict plan nodes, and the known
measurement-group enum. An imported baseline never executes its stored SQL.

The Streamlit workload view links a ranked statement to an explicitly reviewed
representative SQL draft. PostgreSQL `$1`/`$2` placeholders and blank drafts are
blocked before API submission, and the user must confirm local synthetic
`EXPLAIN ANALYZE` execution. The resulting analysis can be saved as a
measurement-grouped baseline without leaving the workload workflow.
