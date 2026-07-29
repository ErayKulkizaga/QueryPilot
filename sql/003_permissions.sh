#!/usr/bin/env bash
set -Eeuo pipefail

: "${QUERYPILOT_POSTGRES_APP_PASSWORD:?QUERYPILOT_POSTGRES_APP_PASSWORD is required}"

psql \
  --set=ON_ERROR_STOP=1 \
  --set=app_password="$QUERYPILOT_POSTGRES_APP_PASSWORD" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" <<'EOSQL'
SELECT format(
    'CREATE ROLE querypilot_app LOGIN PASSWORD %L',
    :'app_password'
)
WHERE NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles WHERE rolname = 'querypilot_app'
)
\gexec

SELECT format(
    'ALTER ROLE querypilot_app PASSWORD %L',
    :'app_password'
)
\gexec

GRANT CONNECT ON DATABASE querypilot TO querypilot_app;
GRANT USAGE ON SCHEMA public TO querypilot_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO querypilot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO querypilot_app;
EOSQL
