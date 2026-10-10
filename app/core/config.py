from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Typed application settings, loaded from environment variables and an optional .env file.

    Secret values use SecretStr so they are masked in reprs, logs and validation errors.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: LogLevel = "INFO"

    database_url: SecretStr = Field(
        description="SQLAlchemy URL using the psycopg driver, e.g. postgresql+psycopg://user:pass@host/db",
    )
    frontend_origin: str = Field(
        default="http://localhost:5173",
        description="Single origin allowed by CORS. Use the exact scheme, host and port.",
    )

    # AI configuration. Providers are disabled by default; no external call happens unless
    # a provider is explicitly selected and its key is supplied.
    llm_provider: Literal["none", "gemini"] = "none"
    llm_model: str = ""
    gemini_api_key: SecretStr | None = None
    embedding_provider: Literal["none", "local", "gemini"] = "none"

    @field_validator("database_url")
    @classmethod
    def _require_psycopg_driver(cls, value: SecretStr) -> SecretStr:
        # The error text deliberately omits the value: the URL contains a password.
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg:// scheme")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns the process-wide settings. Read-only after the first call.

    Tests that change environment variables must call ``get_settings.cache_clear()``.
    """
    return Settings()
