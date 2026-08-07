# QueryPilot security review

Reviewed for the final `v2.0.1` portfolio release.

## Hosting boundary

- The QueryPilot repository does not have an active GitHub Pages site; the
  GitHub Pages API returns `404`.
- `querypilot.eraykulkizaga.com` resolves through a CNAME to
  `custom-domains.chatgpt.site`.
- The public application is deployed through Sites on Cloudflare. GitHub stores
  source code only; it does not receive the Gemini runtime secret.

## SQL injection boundary

The public demo accepts EXPLAIN JSON, not SQL. It has no PostgreSQL binding,
database credential, or SQL execution path, so its AI endpoint cannot be used
for SQL injection.

The separate local runtime applies layered controls before `EXPLAIN ANALYZE`:

1. PostgreSQL SQL is parsed as an AST with SQLGlot.
2. Exactly one statement is accepted.
3. Only `SELECT` or `WITH ... SELECT` query ASTs are accepted.
4. Data-changing, locking, transaction, command, copy, and `SELECT INTO` nodes
   are rejected.
5. Known side-effect functions and all unknown/user-defined functions are
   rejected.
6. PostgreSQL runs the validated statement in a read-only transaction with a
   statement timeout and a least-privilege application role.

Tests cover stacked statements, data-changing CTEs, row locks, side-effect
functions, user-defined functions, statement-like text inside string literals,
and statement-like text inside comments.

This remains an educational local tool. It must not receive production
credentials or run unreviewed queries against a production database.

## Public AI boundary

- The complete pasted EXPLAIN JSON stays in the visitor's browser.
- Only a bounded category, severity, and fixed-shape evidence payload is
  accepted by the same-origin Worker endpoint.
- User-submitted summaries are replaced with an application-owned canonical
  summary before prompting.
- Evidence fields must match the exact metric shape for their deterministic
  category; prompt-like evidence and unsafe identifiers are rejected.
- A category-owned PostgreSQL knowledge chunk is selected server-side.
- Model output must use known evidence and citation IDs.
- Invented numbers, URLs, SQL action commands, unknown backticked identifiers,
  HTML markup, extra fields, and malformed JSON are rejected.
- Provider failures, invalid output, timeout, quota exhaustion, or a missing
  key leave the deterministic result unchanged.
- Provider calls have a 15-second timeout and a best-effort per-client,
  per-isolate request limit. The Gemini project remains on its free tier so
  quota abuse can exhaust availability but cannot silently create paid usage.

## API-secret boundary

- `GEMINI_API_KEY` exists only as a secret production runtime value in Sites.
- `.env*` files are ignored; only a placeholder `.env.example` is tracked.
- The key is read from the Worker runtime environment and is never returned in
  an API response.
- Provider error bodies are not forwarded to visitors.
- The browser bundle test rejects the Gemini endpoint, runtime variable name,
  or Google API-key-shaped values in client JavaScript.
- The release gate scans tracked files for secret patterns before deployment.
- GitHub secret scanning and push protection are enabled for the repository.
- CodeQL analyzes the Python and JavaScript/TypeScript source on every push and
  pull request.
- Private vulnerability reporting is enabled; disclosure instructions live in
  the root `SECURITY.md` file.

## Browser response hardening

The Worker adds content-type, framing, referrer, permissions, transport,
cross-origin, and Content Security Policy headers. The API accepts JSON POST
requests from the same origin and returns `no-store` responses.

## Review result

No known critical SQL-injection or API-key-leakage path remains within the
documented public and local boundaries. This review is an automated and manual
engineering assessment, not a third-party penetration test.
