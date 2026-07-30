# QueryPilot public demo

This directory contains the database-free portfolio surface deployed at
[querypilot.eraykulkizaga.com](https://querypilot.eraykulkizaga.com/).

It accepts a bundled fixture or pasted PostgreSQL `EXPLAIN (FORMAT JSON)`
output and performs deterministic analysis entirely in the visitor's browser.
It never executes SQL or connects to PostgreSQL.

When deterministic plan evidence exists, the visitor may separately request an
AI + RAG explanation. Only the category, severity, short finding, and evidence
list are sent to the same-origin Worker. The complete EXPLAIN JSON stays in the
browser. The Worker retrieves one category-owned PostgreSQL knowledge chunk,
calls Gemini, and validates the model output before displaying it.

## Supported diagnoses

- potential missing index
- expensive nested loop
- disk-based sort
- cardinality misestimation
- explicit no-clear-issue result when evidence is insufficient

Input is limited to 200 KB and 250 plan nodes. Citation-like fields in submitted
JSON are ignored; citations come only from the application's category-specific
PostgreSQL documentation allowlist.

The optional AI endpoint additionally enforces:

- same-origin JSON requests capped at 8 KB
- no AI call for the no-clear-issue path
- server-only API credentials
- a 15-second provider timeout
- exact evidence and citation ID allowlists
- rejection of invented numbers, identifiers, URLs, and SQL change commands
- deterministic fallback on invalid output, provider errors, or free-quota
  exhaustion

## Local development

Requires Node.js 22.13 or later.

```powershell
npm install
Copy-Item .env.example .env
# Add a dedicated Gemini free-tier key to the ignored .env file.
npm run dev
```

## Verification

```powershell
npm run lint
npm test
```

`npm test` builds the production bundle, verifies the rendered application
shell, and runs the deterministic analyzer and public-AI contract tests,
including malformed input, oversized input, node-limit, no-answer,
citation-boundary, invented-number, and unknown-source cases. Provider calls
are not made during the default test suite.

## Implementation map

- `app/query-pilot-demo.tsx` - interface and client-side workflow
- `lib/analyzer.ts` - plan normalization, safety limits, and deterministic rules
- `lib/public-ai.ts` - bounded public RAG prompt and model-output validator
- `lib/fixtures.ts` - synthetic demonstration plans
- `tests/analyzer.test.ts` - public analysis and trust-boundary tests
- `tests/public-ai.test.ts` - public AI evidence and citation contract tests
- `public/og.png` - QueryPilot social preview

The full local engineering runtime lives at the repository root. See the
[architecture document](../docs/architecture.md) for the boundary between the
public demo and the PostgreSQL/FastAPI/Foundry Local implementation.
