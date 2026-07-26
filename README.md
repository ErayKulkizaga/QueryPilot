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
[Release checklist](docs/release-checklist.md)

![QueryPilot public demo showing a deterministic PostgreSQL plan diagnosis](artifacts/screenshots/querypilot-live-desktop.png)

The public demo is intentionally database-free: pasted `EXPLAIN (FORMAT JSON)`
plans are analyzed inside the browser. The full local runtime adds PostgreSQL,
FastAPI, Streamlit, local retrieval, and optional Foundry Local enrichment.

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

Open `http://127.0.0.1:8000/docs` and verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

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

Project delivery references:

- [`docs/architecture.md`](docs/architecture.md) — local and public runtime
  boundaries
- [`docs/demo-script.md`](docs/demo-script.md) — evidence-first five-minute demo
- [`docs/release-checklist.md`](docs/release-checklist.md) — automated and
  manual release gates

Run the default release gate without starting Docker or Foundry Local:

```powershell
python -m scripts.release_check
```

Run the complete API smoke test while PostgreSQL is available:

```powershell
docker compose up -d
python -m scripts.api_smoke
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
