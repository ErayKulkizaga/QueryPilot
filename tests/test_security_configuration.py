from pathlib import Path

from app.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_postgres_is_bound_to_loopback_with_configurable_credentials() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert '127.0.0.1:${QUERYPILOT_POSTGRES_PORT:-5432}:5432' in compose
    assert "QUERYPILOT_POSTGRES_OWNER_PASSWORD" in compose
    assert "QUERYPILOT_POSTGRES_APP_PASSWORD" in compose


def test_database_role_bootstrap_does_not_embed_the_app_password() -> None:
    bootstrap = (ROOT / "sql" / "003_permissions.sh").read_text(encoding="utf-8")

    assert "QUERYPILOT_POSTGRES_APP_PASSWORD" in bootstrap
    assert "querypilot_app_dev" not in bootstrap
    assert "GRANT SELECT ON ALL TABLES" in bootstrap


def test_local_regression_threshold_uses_reviewed_noise_floor() -> None:
    settings = Settings(_env_file=None)

    assert settings.regression_execution_ratio == 1.5
    assert settings.regression_execution_delta_ms == 15.5
    assert settings.regression_cost_ratio == 1.25
