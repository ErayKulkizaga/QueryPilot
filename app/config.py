from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QUERYPILOT_",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = Field(
        default="postgresql://querypilot_app:querypilot_app_dev@localhost:5432/querypilot"
    )
    statement_timeout_ms: int = Field(default=3000, ge=100, le=30_000)
    foundry_app_name: str = "querypilot_local"
    foundry_chat_model: str = "qwen2.5-1.5b"
    foundry_embedding_model: str = "qwen3-embedding-0.6b"
    generation_repair_cutoff_seconds: float = Field(default=8.0, ge=0, le=60)
    analysis_ttl_seconds: int = Field(default=900, ge=60, le=86_400)


@lru_cache
def get_settings() -> Settings:
    return Settings()
