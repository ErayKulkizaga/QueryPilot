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

The sentence-ID experiment was superseded by a real grounded-generation
contract. Foundry Local now calls `submit_grounded_report` with four fields:

- `summary`
- `recommendation`
- `evidence_ids`
- `citation_ids`

The model receives deterministic plan evidence and the text of
category-supporting chunks retrieved by local embeddings. It writes the
human-facing summary and recommendation, but category, severity, raw evidence,
recommendation SQL, and no-answer state remain application-owned.

The validator rejects unknown evidence or chunk IDs, duplicate IDs, invented
numbers, unknown backticked identifiers, untrusted URLs, SQL-like change
instructions, extra fields, and malformed tool arguments. Citations are built
only from accepted retrieved chunk IDs. A known but category-irrelevant
document is not passed to generation.

A repair is attempted only when the first invalid response completes within
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
- accepted grounded generations: 100% (4/4 generation samples)
- valid response citations: 100% (4/4 generation samples)

The security design worked as intended: retrieval supplied only known source
chunks, all four real model generations passed the grounding contract, and
invalid synthetic outputs fell back to the evidence-backed report.

## Grounded model measurement

The current four-case grounded-generation evaluation used
`qwen2.5-1.5b`:

| Metric | Result |
| --- | ---: |
| Accepted grounded generations | 4/4 |
| Valid retrieved citations | 4/4 |
| Average generation latency | 48,256 ms |
| Generation p95 latency | 55,668 ms |

The previous 0.5B/1.5B sentence-selection comparison remains historical and is
not directly comparable to this more demanding prose-generation task. The
1.5B model remains outside the primary response path because CPU generation is
slow, not because it is absent from the product.

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
