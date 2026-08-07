# Security policy

## Supported version

QueryPilot is a frozen portfolio project. The final supported release is
`v2.0.1`; no feature-development roadmap is active.

## Reporting a vulnerability

Please do not disclose a suspected vulnerability in a public issue. Use
GitHub's **Report a vulnerability** option in the repository Security tab so
the report and any proof of concept remain private.

Include the affected surface, reproduction steps, expected impact, and whether
the issue concerns the browser demo, server-side AI endpoint, or local runtime.
Do not include real database credentials, API keys, personal data, or production
query plans.

## Security boundaries

- The public demo is database-free and never executes SQL.
- The local runtime is intended for the synthetic fixture or a separately
  authorized non-production database only.
- Public AI receives bounded deterministic evidence, not the complete plan.
- Model output is untrusted until it passes evidence, citation, numeric, URL,
  identifier, HTML, and SQL-action validation.
- Secrets belong only in ignored local environment files or encrypted hosting
  settings.

The engineering assessment and known limitations are documented in
[`docs/security-review.md`](docs/security-review.md). This project has not
received an independent penetration test or formal security certification.
