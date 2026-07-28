# QueryPilot Local — five-minute live demo script

This script is the reproducible walkthrough for presentations and reviewer
verification. A separately recorded video is not required for the `v1.0.0`
technical release.

This script uses the synthetic `missing_customer_email_index` scenario. The
index is applied manually only to the disposable demo database; QueryPilot
never applies recommendation SQL automatically.

## 00:00–00:30 — Problem and boundary

Show the title or public demo landing state.

> Slow PostgreSQL queries are easy to observe but harder to explain safely.
> QueryPilot turns a machine-readable execution plan into a concise,
> evidence-backed finding. The correctness path is deterministic and local;
> the language model is optional.

Call out that the public demo accepts plans only and never executes SQL.

## 00:30–01:10 — Reproduce the slow query

Open the local Streamlit interface and select
`missing_customer_email_index`. Run the deterministic analysis.

Show:

- the query filtering `customers.email`;
- the real PostgreSQL execution time;
- the sequential scan over 25,000 synthetic rows;
- 24,999 rows removed by the filter.

> This is a synthetic database and `EXPLAIN ANALYZE` is intentionally limited
> to the local demo environment.

## 01:10–02:05 — Explain the deterministic finding

Point to the report fields in order:

1. category: `potential_missing_index`;
2. severity: `high`;
3. plan evidence from the sequential scan and filter selectivity;
4. display-only recommendation:
   `CREATE INDEX idx_customers_email ON customers (email);`.

> The recommendation exists because a rule found plan evidence. If no rule has
> enough evidence, QueryPilot returns no clear issue instead of guessing.

## 02:05–03:10 — Show retrieval and the model boundary

Click the optional enrichment action.

Show the PostgreSQL documentation citation and the selected explanation
sentences.

> Retrieval may supply only known local documents. The model cannot write the
> evidence, SQL, category, severity, or citation. It returns two sentence IDs
> from an application-owned list. Unknown IDs, extra prose, invented citations,
> and malformed JSON are rejected. A slow invalid response skips repair and
> falls back immediately.

Mention that `qwen2.5-1.5b` passed 4/4 sentence-selection cases but averaged
20.2 seconds on CPU, which is why enrichment is not on the primary path.

## 03:10–04:00 — Apply the index manually

In a PostgreSQL terminal connected only to the synthetic demo database, copy
the displayed recommendation:

```sql
CREATE INDEX idx_customers_email ON customers (email);
```

Run it manually and return to the same scenario.

> QueryPilot did not make this change. A human reviewed and applied the
> display-only SQL in a disposable environment.

## 04:00–04:35 — Compare before and after

Run the same query again and compare the plan:

- sequential scan before;
- index-backed lookup after, when selected by PostgreSQL;
- measured execution time before and after.

Do not claim a fixed speed-up. Read the actual numbers visible in this run.
For rehearsal, the latest committed seven-run medians are 1.671 ms before and
0.074 ms after; treat them as a reference to reproduce, not a guaranteed result.

## 04:35–05:00 — Close with evidence and limitations

Show the evaluation summary:

- 12/12 rule diagnoses;
- 12/12 no-answer decisions;
- 9/9 retrieval Hit@3 cases;
- 4/4 valid response citations.

Show the final slide with the measured before/after plan, the narrow MVP
limitations, and tool-calling v2 as future work.

Close with the limitations:

> These are small MVP fixtures, not production benchmarks. The supported issue
> set is deliberately narrow, model enrichment is CPU-bound, and production
> changes still require workload testing and DBA review. The central result is
> the trust boundary: no plan evidence means no recommendation.
