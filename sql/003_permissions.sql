DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'querypilot_app') THEN
        CREATE ROLE querypilot_app LOGIN PASSWORD 'querypilot_app_dev';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE querypilot TO querypilot_app;
GRANT USAGE ON SCHEMA public TO querypilot_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO querypilot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO querypilot_app;

