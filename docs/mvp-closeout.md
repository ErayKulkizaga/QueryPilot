# QueryPilot Local MVP closeout

Status: release candidate, 27 July 2026.

## What this MVP proves

QueryPilot Local is not intended to outperform a general-purpose model at
free-form PostgreSQL advice. It demonstrates a stricter trust boundary:

- PostgreSQL plan facts come from a read-only, machine-readable plan.
- Deterministic rules own the diagnosis, severity, evidence, recommendation
  SQL, no-answer decision, and citation allowlist.
- No recommendation is produced without a supported rule-engine finding.
- The optional local model can select only application-approved sentences.
- The public demo runs entirely in the browser and never executes SQL.

This makes the MVP a portfolio-quality safety architecture and a foundation for
an automated database-performance product. It is not a replacement for
production workload testing or DBA review.

## Seven-day report compliance

| Report requirement | Evidence | Status |
| --- | --- | --- |
| Foundry Local chat model | Local 1.5B model smoke and four accepted evaluation samples | Complete |
| Local embeddings and semantic retrieval | Persisted embedding index and 9/9 Hit@3 evaluation | Complete |
| Read-only PostgreSQL EXPLAIN JSON | Select-only role, read-only transaction, timeout, recursive parser | Complete |
| At least four rule categories | Missing index, nested loop, disk sort, cardinality misestimation | Complete |
| Evidence-gated recommendation | No-answer behavior and category-bound citations | Complete |
| Streamlit interface | Scenarios, custom SQL, result, evidence, and raw plan | Complete |
| Twelve-scenario evaluation | Canonical `evaluation/results.json` | Complete |
| Tests and smoke checks | Clean-environment release gate and live scenario artefacts | Complete |
| English README and architecture | `README.md` and `docs/architecture.md` | Complete |
| Screenshots | Desktop and mobile release screenshots | Complete |
| Six-slide technical presentation | Editable PPTX and visually verified PDF | Complete |
| Before/after evidence | Seven-run synthetic fixture benchmark | Complete |
| Limitations and future work | This closeout, architecture, demo script, and final slide | Complete |
| Approximately five-minute recorded demo | Recording script is ready | User recording pending |
| Clean repository and security scan | Secret scan plus Python, Foundry, and npm audits | Complete |
| `v1.0.0` tag and final link check | Tag must include the recorded video link | Pending after video |

## Verified presentation state

- The custom-domain demo was opened at
  `https://querypilot.eraykulkizaga.com/` on 27 July 2026.
- The healthy-plan scenario completed in the browser and returned
  `Öneri üretilmedi`.
- No browser console warning or error was observed.
- The six-slide presentation has no detected overflow and its exported PDF was
  visually reviewed page by page.
- The demo script includes the measured before/after result and a no-answer
  scenario.

The project is ready for a live presentation. The recorded five-minute video is
still required only to make the formal delivery package complete and resilient
when a live demo is unavailable.

## Measured evidence

- Rule diagnosis: 12/12.
- No-answer decisions: 12/12.
- Retrieval Hit@3: 9/9 applicable cases.
- Valid response citations: 4/4 generation samples.
- Accepted 1.5B sentence selections: 4/4.
- Optional CPU selection average: 20.2 seconds.
- Synthetic missing-index benchmark median:
  - before: 1.671 ms, sequential scan;
  - after: 0.074 ms, index scan.

These figures are small fixture results, not production performance claims.

## Known MVP limitations

- Only four performance-signal categories are supported.
- The full local runtime analyzes one submitted query at a time.
- Optional Foundry enrichment is slow on CPU and stays outside the primary
  correctness path.
- The public demo accepts plan JSON but does not connect to a real database.
- Recommendation SQL is display-only and requires workload testing and human
  review.

## Version 2 direction

The next version should move from single-plan explanation to automated
performance triage:

1. Read `pg_stat_statements` through a least-privilege integration.
2. Rank expensive and frequently executed queries automatically.
3. Store plan baselines and detect regressions between releases.
4. Compare before/after plans and measured timings as first-class evidence.
5. Add CI checks for known query-plan regressions.
6. Produce a team-facing evidence report instead of only an individual answer.

Tool-calling may be explored in version 2, but it must remain behind the same
deterministic evidence and authorization boundaries.

## Freeze decision

Version 1 scope is frozen. The only remaining version 1 actions are:

1. record the five-minute demo using `docs/demo-script.md`;
2. add the video link to the delivery package;
3. update versions to `1.0.0`;
4. run the final gate;
5. create and push the `v1.0.0` tag.

All product expansion belongs to version 2.
