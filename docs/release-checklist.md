# QueryPilot final release checklist

## Automated gate

Run from the repository root:

```powershell
python -m scripts.release_check
```

The gate verifies required artifacts, version consistency, relative Markdown
links, tracked secrets, Python and npm dependency advisories, at least 80%
Python coverage, Ruff correctness and security rules, and the public-demo
lint/build/test suite.

GitHub Actions additionally starts a fresh PostgreSQL fixture and verifies
workload ranking, least-privilege access, guarded pilot measurement,
multi-sample baseline comparison, named plan contracts, and the real-browser
Streamlit workflow. The fixture is always removed afterward.

## Functional acceptance

- [x] Deterministic JSON plan normalization and four evidence-backed diagnoses
- [x] Explicit no-answer behavior when plan evidence is insufficient
- [x] AST-validated, single-statement, read-only local SQL execution
- [x] Least-privilege `pg_stat_statements` workload ranking
- [x] Representative-SQL handoff for parameterized workload statements
- [x] Measurement-grouped multi-sample plan baselines
- [x] Evidence-threshold plan-regression detection
- [x] Strict baseline import/export and Markdown evidence reports
- [x] Streamlit workflow and FastAPI contract
- [x] Database-free public plan analyzer and synthetic V2 showcase

## AI and RAG acceptance

- [x] Six local PostgreSQL sources and 24 citation-ready chunks
- [x] Foundry Local embedding retrieval and structured generation
- [x] Optional public Gemini explanation using bounded evidence only
- [x] Evidence and citation ID allowlists
- [x] Numeric, URL, identifier, HTML, SQL-action, and schema validation
- [x] Prompt-like evidence rejected before model invocation
- [x] One bounded local repair attempt followed by deterministic fallback
- [x] No AI call or recommendation when deterministic evidence is insufficient

## Security acceptance

- [x] Public demo has no database credential or SQL execution path
- [x] PostgreSQL bound to loopback with a read-only application role
- [x] Statement timeout and read-only transaction enforced
- [x] Hosted Gemini key stored only as an encrypted server runtime secret
- [x] Browser bundle and tracked-file secret scans
- [x] Same-origin JSON endpoint, payload limits, timeout, rate limiting, and
  hardened response headers
- [x] GitHub secret scanning and push protection enabled
- [x] CodeQL enabled for Python and JavaScript/TypeScript
- [x] Private vulnerability reporting and root security policy enabled
- [x] Third-party GitHub Actions pinned to reviewed commit SHAs

## Evidence and delivery acceptance

- [x] 103 Python tests at 88.68% coverage
- [x] 19 public-demo tests
- [x] Fresh PostgreSQL workload, permission, baseline, plan-contract, and pilot
  checks in CI
- [x] Real-browser Streamlit workflow in CI
- [x] Reproducible seven-run before/after benchmark
- [x] Versioned evaluation and smoke artifacts
- [x] Architecture, security review, technical presentation, and screenshots
- [x] Live custom-domain demo with TLS and grounded public-AI smoke
- [x] MIT license, repository metadata, release notes, and final closeout
- [x] Commercial SaaS capabilities explicitly excluded from scope
- [x] Final `v2.0.1` tag and GitHub Release published

## Release decision

`v2.0.1` is the final frozen CV and technical-portfolio release. The tag must
point to the exact commit that passes the automated gate and is deployed to the
public demo. No recorded video is required.
