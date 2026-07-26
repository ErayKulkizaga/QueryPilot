# Technical spike - 24 July 2026

## Environment

- Windows demo machine
- Python 3.13 virtual environment
- PostgreSQL 17 in Docker Desktop
- Foundry Local SDK WinML 1.2.3
- OpenAI Python 2.48.0 (transitive Foundry SDK requirement)
- CPU execution provider

## PostgreSQL result

The seeded `missing_customer_email_index` scenario completed through the
FastAPI endpoint. PostgreSQL returned a real JSON execution plan with a
sequential scan over 25,000 synthetic customers and 24,999 rows removed by the
email filter. The deterministic rule engine returned:

- category: `potential_missing_index`
- severity: `high`
- recommendation SQL: `CREATE INDEX idx_customers_email ON customers (email);`

## Foundry Local result

Both P0 model aliases were present in the live catalog and downloaded:

| Purpose | Alias | Download size | Runtime |
| --- | --- | ---: | --- |
| Chat | `qwen2.5-0.5b` | 822 MB | CPUExecutionProvider |
| Embeddings | `qwen3-embedding-0.6b` | 495 MB | CPUExecutionProvider |

The embedding model returned two vectors with 1,024 dimensions each.

The chat model produced a response locally, but changed the supplied evidence
value from 24,999 to 249,990. A second cached run invented a 25% selectivity
claim. The smoke script's numeric-integrity check rejected both results. This
is an observed reliability failure, not a theoretical risk.

## Engineering decision

The chat model must never be the source of technical plan facts. Generation is
limited to a short summary and recommendation explanation. Category, severity,
plan evidence, recommendation SQL, citations, and no-answer state are assembled
by the application from deterministic findings and retrieved context.

The 0.5B model remains useful for the initial offline integration spike. Model
quality will be measured during evaluation before choosing whether a larger
local chat model is justified for the final demo.

## Local retrieval result

The six-document knowledge base produced 24 heading-aware chunks. Foundry Local
embedded every chunk into a 1,024-dimensional vector and the index was persisted
as a compressed NumPy archive plus JSON metadata.

The initial four-case retrieval evaluation achieved:

- Top-1 accuracy: 100% (4/4)
- Hit@3: 100% (4/4)
- Average query latency: 4,440 ms on CPU, including a 9,041 ms cold first query

This is a small integration set, not a final quality claim. The final evaluation
must include paraphrases, ambiguous queries, and negative or insufficient-context
cases before retrieval metrics are used in the presentation or CV.

## Grounded generation result

The first full-report contract required the model to reproduce every structured
field. Two invalid attempts produced a safe fallback but made the complete API
request take 42,978 ms. Reducing the contract to two prose fields improved
latency, but a live UI test exposed a semantic contradiction that passed the
numeric and schema checks. Free-form model prose was therefore removed.

The final contract accepts only:

- `summary_sentence_id`
- `recommendation_sentence_id`

Both values must be exact IDs from category-specific sentences authored by the
application. The model cannot write or rewrite displayed text. Unknown IDs,
extra fields, model-authored text, and malformed JSON are rejected.

Retrieved citations are attached only when their document ID is the configured
primary source for the detected category. A known but irrelevant retrieved
document is not cited. The rule engine remains the source of category,
severity, evidence, recommendation SQL, and the allowed sentence set.

A repair is attempted only when the first invalid selection completes within
eight seconds. Otherwise the service immediately returns the deterministic
fallback.

## Split API and 12-scenario evaluation

The API now separates the primary analysis from optional generation:

- `POST /api/v1/analyses` runs SQL validation, PostgreSQL `EXPLAIN`, plan
  parsing, and deterministic rules.
- `POST /api/v1/analyses/{analysis_id}/enrichment` runs retrieval and local
  generation only when requested.

The first live deterministic request completed in 208 ms. A later end-to-end
Streamlit run completed the deterministic path in 546 ms, including UI-to-API
communication and a real PostgreSQL plan.

The expanded fixture evaluation contains 12 cases across four supported issue
categories plus healthy and edge-case no-answer plans. Results:

- rule diagnosis accuracy: 100% (12/12)
- no-answer accuracy: 100% (12/12)
- retrieval Hit@3: 100% (9/9 applicable cases)
- valid response citations: 100% (4/4 selection samples)

The security design worked as intended: retrieval supplied only known sources,
the model could not create or select citations, and all invalid selections fell
back to the evidence-backed report.

## Chat model comparison

The same four sentence-selection cases were run with both local chat models:

| Metric | `qwen2.5-0.5b` | `qwen2.5-1.5b` |
| --- | ---: | ---: |
| Accepted selections | 1/4 | 4/4 |
| Valid response citations | 4/4 | 4/4 |
| Average selection latency | 12,633 ms | 20,243 ms |
| Selection p95 latency | 24,104 ms | 30,444 ms |

The 1.5B model is the default optional enrichment model. It adds roughly 1 GB
of local download size and remains too slow for the primary response path, but
its sentence-selection reliability is materially better than the 0.5B
candidate. Because displayed text comes from the application-owned sentence
set, selection cannot introduce a new plan claim.

## Public demo architecture

The portfolio demo is intentionally separated from the full local runtime. It
runs the deterministic plan parser and the four rule categories directly in
the browser. It has no PostgreSQL connection, SQL execution, model inference,
embedding request, or application-owned persistence.

The public boundary adds:

- five synthetic, user-selectable plan fixtures
- pasted PostgreSQL `EXPLAIN (FORMAT JSON)` support
- a 200 KB input limit and 250-node plan limit
- category-bound PostgreSQL documentation citations
- explicit no-answer behavior when no strong signal is found
- Turkish explanations and responsive keyboard-accessible controls

Input JSON cannot control a citation. Known citation metadata is authored by
the application and selected only after a deterministic rule category is
established. The full local FastAPI, PostgreSQL, RAG, and Foundry Local path
remains available as the engineering version of the project.
