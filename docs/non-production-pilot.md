# Authorized non-production pilot

The pilot runner measures an explicit allowlist of representative `SELECT`
queries against a separately authorized PostgreSQL target. It is portfolio
evidence for the V2 workflow, not permission to connect QueryPilot to
production.

## Safety gates

The runner refuses to continue unless all of these conditions are met:

- the operator passes `--acknowledge-authorized-non-production`;
- the connection URL comes from `QUERYPILOT_PILOT_DATABASE_URL`, never from the
  manifest or a command-line argument;
- the connected database name matches `--expected-database`;
- the connected role is not a superuser and cannot create roles/databases,
  replicate, or bypass row-level security;
- the transaction reports `transaction_read_only = on`;
- every manifest entry is one parseable `SELECT` or `WITH ... SELECT`;
- PostgreSQL placeholders such as `$1` and `$2` have been replaced with
  reviewed representative literals;
- statement and lock timeouts are active.

The default mode requests `EXPLAIN (FORMAT JSON)` and does not execute the
allowlisted query. `--allow-explain-analyze` is a separate explicit switch
because PostgreSQL then executes each `SELECT` for the manifest's configured
number of repetitions.

## Prepare the target

Ask the target owner or DBA for:

1. written authorization for a non-production database;
2. a dedicated login with only the `CONNECT`, schema `USAGE`, and table/view
   `SELECT` rights required by the manifest;
3. the exact expected database name;
4. reviewed representative values and a controlled measurement window.

Do not use an owner, migration, application-write, cloud-admin, or production
credential.

Copy [`contracts/pilot_queries.example.json`](../contracts/pilot_queries.example.json)
and replace its synthetic entries with explicitly approved queries. Keep
sensitive real-world manifests outside the repository.

## First pass: non-executing plan check

In PowerShell, set the connection only for the current process:

```powershell
$env:QUERYPILOT_PILOT_DATABASE_URL = '<authorized read-only PostgreSQL URL>'
python -m scripts.non_production_pilot `
  C:\secure\querypilot-pilot.json `
  --expected-database '<exact database name>' `
  --output C:\secure\querypilot-plan-only.json `
  --acknowledge-authorized-non-production
```

Review the target metadata, query fingerprints, root plan types, node counts,
and costs. The report never contains the connection URL or password.

## Second pass: controlled timing calibration

Only after the plan-only report and measurement window are approved:

```powershell
python -m scripts.non_production_pilot `
  C:\secure\querypilot-pilot.json `
  --expected-database '<exact database name>' `
  --output C:\secure\querypilot-calibration.json `
  --acknowledge-authorized-non-production `
  --allow-explain-analyze
```

The report uses the median and median absolute deviation of three to nine
samples. It proposes conservative execution-time ratio and absolute-delta
values. QueryPilot does not write these values into configuration, generate an
optimization recommendation, or apply SQL. A human must review them with the
DBA and record the final decision.

## What the report can and cannot prove

It can show that the allowlisted queries were planned or measured through a
least-privilege, read-only session under a declared cache label. It cannot
prove production safety, capacity, representative traffic distribution, or the
benefit of a schema change. Cold/warm cache remains an operator-controlled
label; QueryPilot does not clear PostgreSQL or operating-system caches.
