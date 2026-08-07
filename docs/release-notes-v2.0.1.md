# QueryPilot v2.0.1

QueryPilot `v2.0.1` is the final portfolio-polish release. It does not expand
the product scope established in `v2.0.0`; it improves presentation,
reproducibility, and repository security.

## Changes

- Reworked the root README around the problem, evidence-first architecture,
  AI/RAG boundary, live walkthrough, measured results, and local quick start.
- Added a responsible-disclosure security policy.
- Added release-time validation for relative Markdown links.
- Pinned third-party GitHub Actions to reviewed commit SHAs and disabled
  persisted checkout credentials.
- Added CodeQL analysis for Python and JavaScript/TypeScript.
- Removed unused starter assets from the public-demo source.
- Corrected public-demo documentation to reference the active social-preview
  image.
- Added complete Python package metadata and project links.

## Verification

- 103 Python tests with 88.68% coverage.
- 19 public-demo behavior, integration, and rendered-shell tests.
- Real PostgreSQL workload, permission, plan-contract, and baseline checks in CI.
- Real-browser Streamlit workflow in CI.
- CodeQL analysis for both application languages.
- Python and npm dependency audits with zero known advisories at release.
- Live browser analysis and grounded public-AI request through the custom domain.

## Scope

This remains a completed CV and technical-portfolio project. No commercial
SaaS, production database access, account system, billing, or multi-tenant
credential storage is implied.
