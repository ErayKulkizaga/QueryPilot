# QueryPilot Local

QueryPilot Local is an offline-first PostgreSQL execution-plan assistant. Its
deterministic core validates a read-only SQL query, obtains machine-readable
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, recursively normalizes the plan tree,
and reports evidence-backed performance signals.

This repository is the implementation of the seven-day MVP plan in
`QueryPilot_Local_7_Gunluk_Proje_Raporu.pdf`.

[Live demo](https://querypilot.eraykulkizaga.com/) ·
[Architecture](docs/architecture.md) ·
[Technical presentation](artifacts/QueryPilot_Local_Teknik_Sunum.pdf) ·
[Release checklist](docs/release-checklist.md) ·
[MVP closeout](docs/mvp-closeout.md)

**Release:** `v1.0.0` technical MVP. The delivery package consists of the
working source, automated evaluation, recorded smoke artefacts, screenshots,
architecture documentation, and the technical presentation. A recorded demo
video is intentionally not part of the release scope; `docs/demo-script.md`
remains the reproducible live walkthrough.

![QueryPilot public demo showing a deterministic PostgreSQL plan diagnosis](artifacts/screenshots/querypilot-live-desktop.png)

The public demo is intentionally database-free: pasted `EXPLAIN (FORMAT JSON)`
plans are analyzed inside the browser. The full local runtime adds PostgreSQL,
FastAPI, Streamlit, local retrieval, and optional Foundry Local enrichment.

The MVP is a safety-architecture demonstration, not an attempt to replace a
general-purpose model or a DBA. Its differentiator is enforced behavior:
evidence and known citations are required before a recommendation can exist.
The planned version 2 direction is automated query triage and plan-regression
detection using `pg_stat_statements`.

## Current milestone

The first working slice includes:

- AST-based single-statement and read-only SQL validation
- read-only PostgreSQL execution with a three-second statement timeout
- recursive JSON plan parsing
- deterministic rules for missing-index signals, expensive nested loops,
  disk-based sorts, and cardinality misestimation
- FastAPI health and analysis endpoints
- a seeded PostgreSQL demo environment
- unit and API tests
- six PostgreSQL knowledge documents and 24 citation-ready chunks
- a persisted NumPy cosine-similarity index using Foundry Local embeddings
- top-3 retrieval and a reproducible retrieval evaluation runner
- strict structured report validation and retrieved-citation allowlisting
- numeric evidence integrity, one bounded repair attempt, and deterministic fallback
- a fast deterministic analysis endpoint and separate optional AI enrichment
- a Streamlit interface for sample scenarios and custom read-only SQL
- a 12-scenario rule, no-answer, retrieval, and generation evaluation
- a database-free public demo that analyzes sample or pasted EXPLAIN JSON
  entirely in the browser
- a least-privilege `pg_stat_statements` workload view and deterministic
  total-execution-time ranking API
- persistent local plan baselines and same-query deterministic plan comparison
- evidence-threshold regression alerts for execution time, root cost, and
  index-backed access changing to a sequential scan
- a GitHub Actions release gate covering dependency audits, Python tests,
  minimum coverage, security lint, live PostgreSQL checks, and public-demo tests

## Local setup

Prerequisites: Python 3.11 or later and Docker Desktop.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
docker compose up -d
uvicorn app.main:app --reload
```

PostgreSQL is bound to `127.0.0.1` by default, so the development fixture is
not exposed to other devices on the network. On a shared machine, change both
PostgreSQL passwords and their matching database URLs in the ignored `.env`
file before recreating the fixture.

Existing QueryPilot Docker volumes created before workload prioritization do
not contain the extension or restricted view. Because the local database is a
synthetic fixture, recreate only this project's volume once when upgrading:

```powershell
docker compose down -v
docker compose up -d
```

This removes the locally seeded QueryPilot fixture data and recreates it; it
does not affect other Docker projects.

If port `5432` is already occupied, select another host port and use the same
port in the application connection string:

```powershell
$env:QUERYPILOT_POSTGRES_PORT = "5433"
$env:QUERYPILOT_DATABASE_URL = "postgresql://querypilot_app:querypilot_app_dev@127.0.0.1:5433/querypilot"
docker compose up -d
```

Open `http://127.0.0.1:8000/docs` and verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

List eligible SELECT statements ranked by total execution time:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/workload/queries?limit=10"
```

The workload endpoint returns ranking evidence only. It does not execute a
captured statement, create an index, or produce an optimization recommendation.
PostgreSQL-normalized `$1`/`$2` statements require representative parameter
values before they can be submitted separately to plan analysis.

The committed workload smoke run executed a sequential `orders` aggregate six
times and a primary-key lookup fifteen times. The aggregate ranked first by
total execution time, only two user-workload queries remained after
infrastructure filtering, and direct `pg_stat_statements` access from the
application role was denied.

After analyzing a query, store its current plan as a local baseline:

```powershell
$baselineBody = @{
  analysis_ids = @("<analysis-id-1>", "<analysis-id-2>", "<analysis-id-3>")
  name = "release-1.0 customer email plan"
} | ConvertTo-Json
$baseline = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/baselines `
  -ContentType application/json `
  -Body $baselineBody
```

Run the same normalized SQL again and compare the new analysis with the
baseline:

```powershell
$comparisonBody = @{
  analysis_ids = @(
    "<new-analysis-id-1>",
    "<new-analysis-id-2>",
    "<new-analysis-id-3>"
  )
} | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/baselines/$($baseline.baseline_id)/comparisons" `
  -ContentType application/json `
  -Body $comparisonBody
```

Baselines are stored locally in SQLite under `data/` by default and are not
committed. Comparison is allowed only when the normalized SQL fingerprint
matches. Up to nine structurally identical plan samples can be aggregated; the
median timing and node metrics are used so one noisy run cannot dominate the
result. Timing regressions must exceed both a ratio and an absolute millisecond
threshold; plan differences never create a recommendation or execute SQL.

Delete a reviewed baseline explicitly:

```powershell
Invoke-RestMethod `
  -Method Delete `
  -Uri "http://127.0.0.1:8000/api/v1/baselines/$($baseline.baseline_id)"
```

The store retains the newest 100 baselines by default. Change this local limit
with `QUERYPILOT_BASELINE_MAX_ITEMS`.

Analyze the missing-index demo:

```powershell
$body = @{ scenario_id = "missing_customer_email_index" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/analyses `
  -ContentType application/json `
  -Body $body
```

Start the user interface in a second terminal:

```powershell
streamlit run streamlit_app.py
```

The deterministic finding appears immediately. If plan evidence and a
category-supporting document are available, the interface offers a separate
button for optional local explanation selection. The model can select only
application-approved sentences; rejected output never replaces the
deterministic report.

## Public demo mode

The `public-demo/` site is the shareable portfolio surface. It does not connect
to PostgreSQL, execute SQL, call a language model, or transmit pasted plan
content to an application API. Its TypeScript analyzer runs in the browser and
supports the same four MVP issue categories plus the no-answer path.

```powershell
Set-Location public-demo
npm install
npm run dev
```

The public input boundary accepts at most 200 KB of JSON and 250 plan nodes.
Citations are selected from a category-specific PostgreSQL documentation
allowlist; citation fields supplied inside input JSON are ignored.

Run tests:

```powershell
pytest
```

Install and verify Foundry Local on the Windows demo machine:

```powershell
python -m pip install -r requirements-foundry.txt
python -m scripts.foundry_spike --download
```

The first Foundry run downloads the configured chat and embedding models. Later
runs reuse the local model cache and can omit `--download`.

Build and evaluate the local retrieval index:

```powershell
python -m scripts.build_index
python -m evaluation.run_retrieval_evaluation
python -m scripts.generation_smoke
python -m evaluation.run_evaluation --with-retrieval --with-generation
```

The generated vector files live under `data/index/` and are intentionally
excluded from Git. Evaluation results are written under `evaluation/`.

Measure the synthetic missing-index fixture before and after the recommended
index. The script restores the fixture without the index when it finishes:

```powershell
python -m scripts.before_after_benchmark
```

The latest committed seven-run medians are 1.671 ms for the sequential scan and
0.074 ms for the index scan. This is a synthetic local-fixture observation, not
a production performance guarantee.

Project delivery references:

- [`docs/architecture.md`](docs/architecture.md) — local and public runtime
  boundaries
- [`docs/demo-script.md`](docs/demo-script.md) — evidence-first five-minute live walkthrough
- [`docs/release-checklist.md`](docs/release-checklist.md) — automated and
  manual release gates
- [`docs/v2-plan-regression.md`](docs/v2-plan-regression.md) — baseline,
  comparison, and regression evidence contract

Run the default release gate without starting Docker or Foundry Local:

```powershell
python -m scripts.release_check
```

The release gate enforces at least 80% Python coverage and runs secret,
dependency, lint, security-lint, build, and behavior checks. GitHub Actions
additionally starts a fresh PostgreSQL fixture and verifies workload ranking,
least-privilege access, and plan-baseline comparison.

Run the complete API smoke test while PostgreSQL is available:

```powershell
docker compose up -d
python -m scripts.api_smoke
python -m scripts.workload_smoke
python -m scripts.baseline_smoke
docker compose stop
```

The model generates no technical prose. It returns only two sentence IDs chosen
from an application-approved, category-specific set. Category, severity,
evidence, recommendation SQL, citations, no-answer state, and displayed
sentences are controlled by the application. If the first invalid selection
exceeds the configured repair cutoff, repair is skipped and the API immediately
uses the deterministic fallback.

## Safety boundary

- Only one `SELECT` or `WITH ... SELECT` statement is accepted.
- Data-changing SQL, `SELECT INTO`, row locks, and known side-effect functions
  are rejected.
- PostgreSQL is accessed through a `SELECT`-only role.
- Every analyzed statement runs in a read-only transaction with a timeout.
- `EXPLAIN ANALYZE` is intended only for the synthetic local demo database.
- Suggested SQL is display-only and is never applied automatically.
- The public demo never executes SQL and accepts plan JSON only.

QueryPilot Local is an educational and portfolio project. It does not replace
production workload testing or DBA review.

## Measured MVP result

The 12-scenario fixture set currently achieves:

- rule diagnosis accuracy: 100% (12/12)
- no-answer accuracy: 100% (12/12)
- retrieval Hit@3: 100% (9/9 applicable cases)
- valid response citations: 100%

Under the sentence-selection contract, `qwen2.5-0.5b` passed one of four cases.
The stronger `qwen2.5-1.5b` model passed all four and is now the default
enrichment model. Its average selection time was 20.2 seconds on CPU, so the
model remains optional and outside the primary correctness path.
