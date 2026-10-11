from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
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

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        # Accept "debug" as well as "DEBUG"; the environment is not always consistent about case.
        return value.upper() if isinstance(value, str) else value

    database_url: SecretStr = Field(
        description="SQLAlchemy URL using the psycopg driver, e.g. postgresql+psycopg://user:pass@host/db",
    )
    frontend_origin: str = Field(
        default="http://localhost:5173",
        description="Single origin allowed by CORS. Use the exact scheme, host and port.",
    )

    # AI configuration. Providers are disabled by default; no external call happens unless
    # a provider is explicitly selected and its key is supplied. No model name is hardcoded:
    # it comes from LLM_MODEL (or GEMINI_MODEL, the name already used in .env).
    llm_provider: Literal["none", "gemini"] = "none"
    llm_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_MODEL", "GEMINI_MODEL"),
    )
    gemini_api_key: SecretStr | None = None
    # When set, LLM responses are cached on disk so reruns are reproducible and free.
    llm_cache_dir: Path | None = None
    embedding_provider: Literal["none", "local", "gemini"] = "none"
    # Upper bound on regulation paragraphs sent to the model in one pipeline run, so a large
    # direction cannot exhaust the model quota. A run can also name the paragraphs to read.
    pipeline_max_paragraphs: int = Field(default=30, gt=0)
    # Retries for rate limits and "model overloaded" answers, with doubling waits in between.
    llm_transport_attempts: int = Field(default=6, ge=1, le=10)
    llm_retry_backoff_seconds: float = Field(default=3.0, gt=0)
    # A run still marked running after this long is treated as abandoned (e.g. server restart).
    pipeline_run_timeout_minutes: int = Field(default=30, gt=0)

    # Sign-in tokens. The secret is never committed: set JWT_SECRET_KEY in .env. When it is unset
    # outside production, a random key is generated per process (tokens end on restart).
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_expire_minutes: int = Field(default=60 * 24, gt=0)
    # Used only by scripts/set_user_passwords.py to set the demo accounts' password. Never read
    # by the running API.
    demo_user_password: SecretStr | None = None

    # Document uploads. Files are written below storage_dir (relative paths resolve against the
    # working directory); the directory is created on first upload, not at import time.
    storage_dir: Path = Path("storage")
    max_upload_mb: int = Field(default=10, gt=0)

    # Time zone used for regulatory deadlines (stored as dates) and "days remaining".
    business_timezone: str = "Asia/Kolkata"

    # Defaults for a drafted remediation when the gap's controls do not supply an owner or
    # closure evidence.
    remediation_default_owner_team: str = "Compliance Operations"
    remediation_default_target_days: int = Field(default=30, gt=0)
    remediation_default_closure_evidence: str = (
        "Updated procedure and signed test results showing the requirement is met."
    )

    # Optional JSON file with the latest evaluation report (EvalReport shape). When it is unset
    # or missing, GET /eval/latest reports that no measured evaluation exists.
    eval_report_path: Path | None = None

    @model_validator(mode="after")
    def _require_model_for_gemini(self) -> "Settings":
        if self.llm_provider == "gemini" and not self.llm_model:
            raise ValueError("LLM_MODEL (or GEMINI_MODEL) must be set when LLM_PROVIDER=gemini")
        return self

    @model_validator(mode="after")
    def _require_jwt_secret_in_production(self) -> "Settings":
        if self.app_env == "production" and self.jwt_secret_key is None:
            raise ValueError("JWT_SECRET_KEY must be set when APP_ENV=production")
        if self.jwt_secret_key is not None and len(self.jwt_secret_key.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return self

    @field_validator("database_url")
    @classmethod
    def _require_psycopg_driver(cls, value: SecretStr) -> SecretStr:
        # The error text deliberately omits the value: the URL contains a password.
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg:// scheme")
        return value

    @field_validator("business_timezone")
    @classmethod
    def _require_known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("BUSINESS_TIMEZONE must be an IANA time zone name") from exc
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns the process-wide settings. Read-only after the first call.

    Tests that change environment variables must call ``get_settings.cache_clear()``.
    """
    return Settings()
