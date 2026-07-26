# QueryPilot public demo

This directory contains the database-free portfolio surface deployed at
[querypilot.eraykulkizaga.com](https://querypilot.eraykulkizaga.com/).

It accepts a bundled fixture or pasted PostgreSQL `EXPLAIN (FORMAT JSON)`
output and performs deterministic analysis entirely in the visitor's browser.
It does not execute SQL, connect to PostgreSQL, call a language model, or send
the submitted plan to an application API.

## Supported diagnoses

- potential missing index
- expensive nested loop
- disk-based sort
- cardinality misestimation
- explicit no-clear-issue result when evidence is insufficient

Input is limited to 200 KB and 250 plan nodes. Citation-like fields in submitted
JSON are ignored; citations come only from the application's category-specific
PostgreSQL documentation allowlist.

## Local development

Requires Node.js 22.13 or later.

```powershell
npm install
npm run dev
```

## Verification

```powershell
npm run lint
npm test
```

`npm test` builds the production bundle, verifies the rendered application
shell, and runs the deterministic analyzer tests, including malformed input,
oversized input, node-limit, no-answer, and citation-boundary cases.

## Implementation map

- `app/query-pilot-demo.tsx` - interface and client-side workflow
- `lib/analyzer.ts` - plan normalization, safety limits, and deterministic rules
- `lib/fixtures.ts` - synthetic demonstration plans
- `tests/analyzer.test.ts` - public analysis and trust-boundary tests
- `public/og.png` - QueryPilot social preview

The full local engineering runtime lives at the repository root. See the
[architecture document](../docs/architecture.md) for the boundary between the
public demo and the PostgreSQL/FastAPI/Foundry Local implementation.
