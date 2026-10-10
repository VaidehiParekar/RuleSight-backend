import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings

VALID_URL = "postgresql+psycopg://app_user:s3cret-value@db.internal:5432/rulesight"


def test_loads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", VALID_URL)
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.test")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.database_url.get_secret_value() == VALID_URL
    assert settings.log_level == "DEBUG"
    assert settings.frontend_origin == "https://app.example.test"
    assert settings.llm_provider == "none"
    assert settings.embedding_provider == "none"


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_rejects_non_psycopg_driver_without_leaking_the_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://app_user:s3cret-value@db.internal/rulesight")

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)  # type: ignore[call-arg]

    message = str(excinfo.value)
    assert "postgresql+psycopg://" in message
    assert "s3cret-value" not in message


def test_secrets_are_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", VALID_URL)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert "s3cret-value" not in repr(settings)
    assert "fake-key-for-test" not in repr(settings)
    assert isinstance(settings.gemini_api_key, SecretStr)
