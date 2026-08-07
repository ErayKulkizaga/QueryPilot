# QueryPilot

> Evidence-first PostgreSQL plan analysis with deterministic diagnostics,
> workload regression checks, and grounded AI + RAG explanations.

[![CI](https://github.com/ErayKulkizaga/QueryPilot/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ErayKulkizaga/QueryPilot/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/ErayKulkizaga/QueryPilot?display_name=tag)](https://github.com/ErayKulkizaga/QueryPilot/releases/latest)
[![License](https://img.shields.io/github/license/ErayKulkizaga/QueryPilot)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Live demo](https://img.shields.io/badge/Live_demo-open-12634A)](https://querypilot.eraykulkizaga.com/)

[**Try the live demo**](https://querypilot.eraykulkizaga.com/) ·
[Architecture](docs/architecture.md) ·
[Security](SECURITY.md) ·
[Technical presentation](artifacts/QueryPilot_Local_Teknik_Sunum.pdf) ·
[Release notes](docs/release-notes-v2.0.1.md)

![QueryPilot — evidence-first plan analysis, workload ranking, and regression detection](public-demo/public/og-v2.png)

## Why QueryPilot exists

A generic LLM can suggest why a SQL query *might* be slow, but it does not own
the database measurements and can invent causes, numbers, or citations.
QueryPilot reverses that relationship:

1. **Measure** — PostgreSQL produces the execution plan and workload counters.
2. **Decide** — deterministic code identifies a supported performance signal.
3. **Ground** — RAG selects only relevant, application-owned PostgreSQL sources.
4. **Explain** — an LLM turns the accepted evidence into concise prose.
5. **Verify** — unknown evidence, citations, metrics, URLs, identifiers, SQL
   actions, or malformed output are rejected.

The model can explain a finding; it cannot create the finding, change its
severity, alter plan evidence, execute SQL, or silently apply an optimization.
If evidence is insufficient, QueryPilot returns an explicit no-answer result.

## What the project demonstrates

| Capability | Full local runtime | Public portfolio demo |
| --- | --- | --- |
| Plan input | Validated read-only SQL and real `EXPLAIN ANALYZE` | Synthetic fixture or pasted `EXPLAIN (FORMAT JSON)` |
| Analysis | Python deterministic rule engine | TypeScript deterministic rule engine in the browser |
| Workload intelligence | Restricted `pg_stat_statements` view and total-time ranking | Database-free synthetic V2 showcase |
| Regression detection | Local multi-sample SQLite baselines | Synthetic before/after comparison |
| AI + RAG | Foundry Local with semantic retrieval | Optional Gemini explanation using bounded evidence |
| Data boundary | Local PostgreSQL and local models | Complete plans stay in the browser; no database connection |

### Core capabilities

- Recursive normalization of PostgreSQL JSON plans.
- Deterministic detection of selective sequential scans, expensive nested
  loops, disk-based sorts, and cardinality misestimation.
- AST-based single-statement, read-only SQL validation with SQLGlot.
- Read-only PostgreSQL execution with a three-second statement timeout.
- Least-privilege workload ranking through `pg_stat_statements`.
- Explicit representative-SQL review for normalized `$1`/`$2` statements.
- Measurement-grouped plan baselines and evidence-threshold regression alerts.
- Six PostgreSQL knowledge documents split into 24 citation-ready chunks.
- Evidence- and citation-bound Foundry Local and Gemini explanation paths.
- Deterministic fallback whenever model output is invalid or unavailable.

## Architecture

```mermaid
flowchart LR
    SQL["Read-only SQL"] --> PG["PostgreSQL EXPLAIN JSON"]
    PG --> RULES["Deterministic rule engine"]
    RULES --> RESULT["Evidence-backed result"]
    RESULT -->|"optional"| RAG["Approved PostgreSQL sources"]
    RAG --> LLM["Foundry Local or Gemini"]
    LLM --> GATE["Evidence and citation validator"]
    GATE -->|"accepted"| REPORT["Grounded explanation"]
    GATE -->|"rejected"| RESULT

    STATS["Restricted workload statistics"] --> RANK["Total-time ranking"]
    RANK --> REVIEW["Representative SQL review"]
    REVIEW --> PG

    PG --> BASE["Local plan baseline"]
    BASE --> COMPARE["Same-query regression comparison"]
```

The [architecture document](docs/architecture.md) describes the local and
public trust boundaries in detail.

## Try the public demo

Open [querypilot.eraykulkizaga.com](https://querypilot.eraykulkizaga.com/),
choose a prepared scenario, and select **Planı analiz et**. You can also paste
your own PostgreSQL `EXPLAIN (FORMAT JSON)` output.

The first result is generated entirely in the browser. For a supported finding,
**AI + RAG ile açıkla** sends only the short deterministic category and evidence
list to the same-origin server endpoint. The complete plan is not sent to the
model. The demo never connects to a database and never executes SQL.

## Local quick start

### Prerequisites

- Python 3.11 or later
- Docker Desktop
- PowerShell

```powershell
git clone https://github.com/ErayKulkizaga/QueryPilot.git
Set-Location QueryPilot

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env

docker compose up -d --wait
uvicorn app.main:app --reload
```

In a second terminal:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run streamlit_app.py
```

- FastAPI documentation: `http://127.0.0.1:8000/docs`
- Streamlit interface: `http://127.0.0.1:8501`

The Docker fixture binds PostgreSQL to `127.0.0.1` only. Development passwords
in `.env.example` are for the synthetic local database and must not be reused
elsewhere.

If port `5432` is already occupied:

```powershell
$env:QUERYPILOT_POSTGRES_PORT = "5433"
$env:QUERYPILOT_DATABASE_URL = "postgresql://querypilot_app:querypilot_app_dev@127.0.0.1:5433/querypilot"
docker compose up -d --wait
```

### Optional local AI + RAG

```powershell
python -m pip install -r requirements-foundry.txt
python -m scripts.foundry_spike --download
python -m scripts.build_index
```

Foundry Local downloads and caches the configured chat and embedding models on
first use. The deterministic analysis path works without those models.

## API workflow

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Runtime health and version |
| `POST /api/v1/analyses` | Validate SQL, obtain a plan, and return deterministic evidence |
| `POST /api/v1/analyses/{id}/enrichment` | Request optional local AI + RAG prose |
| `GET /api/v1/workload/queries` | Rank eligible statements by total execution time |
| `POST /api/v1/baselines` | Save one to nine compatible plan samples |
| `POST /api/v1/baselines/{id}/comparisons` | Compare later samples with a same-query baseline |

Captured workload SQL is never executed automatically. Imported baseline SQL
is validated but never executed. Suggested SQL is display-only.

## Verification and measured results

The release gate runs secret scanning, dependency audits, linting, security
linting, coverage, public build checks, and behavior tests:

```powershell
python -m scripts.release_check
```

GitHub Actions additionally starts a fresh PostgreSQL fixture and verifies
least-privilege workload access, workload ranking, baseline comparison, plan
contracts, a guarded non-production pilot, and a real-browser Streamlit flow.

| Evidence | Final result |
| --- | ---: |
| Python tests | 103 passed |
| Python coverage | 88.68% |
| Public demo tests | 19 passed |
| Rule diagnosis | 12/12 |
| No-answer behavior | 12/12 |
| Retrieval Hit@3 | 9/9 applicable cases |
| Accepted grounded local generations | 4/4 |
| Dependency advisories at release | 0 known |

The committed synthetic missing-index benchmark measured seven-run medians of
`1.671 ms` before the index and `0.074 ms` after it. These are reproducible
fixture results, not production performance claims.

## Security model

- The public demo accepts plan JSON, not SQL, and has no database binding.
- Local SQL is parsed as an AST; stacked, data-changing, locking, side-effect,
  and unknown-function queries are rejected.
- PostgreSQL uses a `SELECT`-only role, read-only transactions, and a timeout.
- Public AI accepts only fixed-shape evidence and application-owned categories.
- Prompt-like evidence and unsafe identifiers are rejected before prompting.
- Model output must reference exact allowlisted evidence and citation IDs.
- API credentials stay in encrypted server runtime settings and are scanned out
  of tracked files and browser bundles.
- Provider errors, timeouts, invalid output, or quota exhaustion preserve the
  deterministic result.

See [SECURITY.md](SECURITY.md) and the detailed
[security review](docs/security-review.md) for reporting instructions, SQL
injection controls, prompt-injection controls, and hosting boundaries.

## Repository map

```text
app/             FastAPI, plan analysis, workload, baseline, RAG, and LLM code
public-demo/     Browser-first portfolio demo and server-side AI endpoint
tests/           Python unit, API, safety, and contract tests
e2e_tests/       Real-browser Streamlit workflow
sql/             Synthetic schema, data, roles, and workload projection
knowledge/       Versioned PostgreSQL RAG source documents
evaluation/      Reproducible fixtures and measured result artifacts
contracts/       Reviewed plan and pilot contracts
docs/            Architecture, security, release, and operating boundaries
artifacts/       Technical presentation and reviewed screenshots
```

## Project status

`v2.0.1` is the final, frozen portfolio release. QueryPilot is an educational
engineering project, not a commercial SaaS service or a replacement for
production workload testing and DBA review. Authentication, billing,
multi-tenant credential storage, and production workload authorization are
deliberately outside its scope.

The implementation began from the seven-day plan in
[`QueryPilot_Local_7_Gunluk_Proje_Raporu.pdf`](QueryPilot_Local_7_Gunluk_Proje_Raporu.pdf).
The final acceptance decision is recorded in
[`docs/v2-closeout.md`](docs/v2-closeout.md).

## License

Released under the [MIT License](LICENSE).
