# QueryPilot v2.0.0

QueryPilot `v2.0.0` is the final portfolio release of an evidence-first
PostgreSQL execution-plan assistant. It combines deterministic plan analysis,
workload prioritization, baseline comparison, and tightly constrained AI + RAG
explanation without allowing the model to own correctness.

## Highlights

- Parses PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` plans and detects
  four measurable performance-signal categories.
- Ranks eligible `pg_stat_statements` entries through a least-privilege view
  while refusing to execute captured parameterized SQL automatically.
- Stores local multi-sample plan baselines and reports same-query regressions
  across compatible measurement groups.
- Uses Foundry Local for offline enrichment and Gemini for the optional public
  explanation path.
- Rejects unknown evidence, citations, numbers, identifiers, URLs, HTML, SQL
  actions, and malformed model output.
- Keeps the public demo database-free; complete pasted plans remain in the
  browser and only bounded evidence can reach the server-side model.

## Verification

- 103 Python tests with 88.68% coverage.
- 19 public-demo behavior, integration, and rendered-shell tests.
- Real-browser Streamlit workflow in CI.
- Fresh PostgreSQL workload, permission, baseline, plan-contract, and guarded
  pilot checks in CI.
- Python and npm dependency audits with zero known vulnerabilities at release.
- Live demo: https://querypilot.eraykulkizaga.com/

## Scope

This is a completed CV and technical-portfolio project, not a commercial SaaS
service. User accounts, billing, multi-tenant credential storage, and
production workload authorization are deliberately out of scope. See
`docs/v2-closeout.md` and `docs/security-review.md` for the exact boundaries.
