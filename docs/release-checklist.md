# QueryPilot Local release checklist

## Automated gate

Run from the repository root:

```powershell
python -m scripts.release_check
```

The default gate keeps Docker and Foundry Local off. It verifies required
delivery files, tracked secrets, Python and npm dependency advisories, at least
80% Python coverage, Ruff correctness and security rules, and the public demo
lint/build/tests.

If PostgreSQL and Foundry Local are already running and a live integration
check is wanted:

```powershell
python -m scripts.release_check --live
```

`--live` does not start or stop Docker; it only runs `scripts.api_smoke`.
GitHub Actions separately starts a fresh PostgreSQL fixture, runs the workload
permission/ranking smoke, guarded pilot calibration, multi-sample baseline
smoke, and real-browser Streamlit workflow, and always removes the fixture
afterward.

## Manual release items

- [x] Deterministic local analysis path
- [x] Evidence-gated no-answer behavior
- [x] Evidence- and citation-bound Foundry Local generation boundary
- [x] Public browser-only demo
- [x] Custom domain and TLS
- [x] English README and measured results
- [x] Architecture document
- [x] MVP closeout and version 2 direction documented
- [x] Five-minute live demo script
- [x] Six-slide technical presentation exported and visually checked
- [x] Final screenshots captured
- [x] Canonical evaluation and API smoke artefacts refreshed
- [x] Reproducible before/after plan benchmark recorded
- [x] Two-scenario API rehearsal recorded from a fresh Docker database
- [x] Grounded Foundry tool calling implemented and measured
- [x] Dependency list reviewed and clean-install compatibility verified
- [x] Release gate passed from a newly created Python environment
- [x] Secret and dependency audits passed with zero remaining findings
- [x] PostgreSQL bound to loopback with configurable local credentials
- [x] Python and npm audits plus minimum coverage enforced in CI
- [x] Fresh PostgreSQL workload and baseline smokes enforced in CI
- [x] V2 workload prioritization preserves evidence-gated recommendations
- [x] V2 live workload ranking and direct-access denial smoke recorded
- [x] Guarded non-production pilot and threshold-calibration runner prepared
- [x] Sanitized synthetic pilot calibration artefact recorded
- [x] Real-browser Streamlit workflow enforced in CI
- [x] Recorded video explicitly removed from the final acceptance scope
- [x] Public source repository confirmed:
  [ErayKulkizaga/QueryPilot](https://github.com/ErayKulkizaga/QueryPilot)
- [x] Version metadata updated to `1.0.0`
- [x] `v1.0.0` release tag created from the final verified commit

The version tag represents the exact commit containing the reviewed
presentation, screenshots, evaluation, smoke artefacts, and reproducible live
walkthrough.
