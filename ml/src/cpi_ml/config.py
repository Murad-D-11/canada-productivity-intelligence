"""Runtime configuration for the ML package.

Values are read from environment variables (and an optional .env file) so the
same code runs locally, in Docker, and in CI without modification.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings.

    The default data-source URLs point at the real, public Government of Canada
    endpoints. They are configurable so tests can target mock servers.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    statcan_wds_base_url: str = Field(
        default="https://www150.statcan.gc.ca/t1/wds/rest",
        alias="STATCAN_WDS_BASE_URL",
    )
    msc_geomet_ogc_api_base_url: str = Field(
        default="https://api.weather.gc.ca",
        alias="MSC_GEOMET_OGC_API_BASE_URL",
    )

    request_delay_ms: int = Field(default=250, alias="DATA_SOURCE_REQUEST_DELAY_MS")
    random_seed: int = Field(default=42, alias="ML_RANDOM_SEED")
    artifacts_dir: str = Field(default="artifacts", alias="ML_ARTIFACTS_DIR")


def get_settings() -> Settings:
    """Return a fresh Settings instance (reads current environment)."""
    return Settings()
