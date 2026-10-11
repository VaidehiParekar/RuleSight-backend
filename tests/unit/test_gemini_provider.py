from types import SimpleNamespace
from typing import Any

import pytest
from google.genai.errors import APIError
from pydantic import BaseModel

from app.integrations.llm.base import LLMProviderError
from app.integrations.llm.cache import FileCache, MemoryCache
from app.integrations.llm.gemini import GeminiProvider


class Answer(BaseModel):
    value: int


class FakeModels:
    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls = 0

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(text=self._texts.pop(0))


class FakeClient:
    def __init__(self, texts: list[str]) -> None:
        self.models = FakeModels(texts)


def _provider(
    texts: list[str], cache: MemoryCache | None = None
) -> tuple[GeminiProvider, FakeClient]:
    client = FakeClient(texts)
    provider = GeminiProvider(
        api_key="unused-in-tests",
        model="test-model",
        cache=cache,
        client=client,  # type: ignore[arg-type]
    )
    return provider, client


def test_returns_validated_answer() -> None:
    provider, _ = _provider(['{"value": 7}'])
    assert provider.generate_structured(prompt="p", schema=Answer, timeout_seconds=5) == Answer(
        value=7
    )


def test_identical_prompt_is_served_from_cache() -> None:
    cache = MemoryCache()
    provider, client = _provider(['{"value": 7}'], cache)
    provider.generate_structured(prompt="same", schema=Answer, timeout_seconds=5)
    again = provider.generate_structured(prompt="same", schema=Answer, timeout_seconds=5)
    assert again.value == 7
    assert client.models.calls == 1


def test_file_cache_survives_a_new_provider(tmp_path: Any) -> None:
    cache_dir = tmp_path / "llm"
    first, _ = _provider(['{"value": 3}'], cache=FileCache(cache_dir))  # type: ignore[arg-type]
    first.generate_structured(prompt="p", schema=Answer, timeout_seconds=5)

    second_client = FakeClient([])
    second = GeminiProvider(
        api_key="unused",
        model="test-model",
        cache=FileCache(cache_dir),
        client=second_client,  # type: ignore[arg-type]
    )
    assert second.generate_structured(prompt="p", schema=Answer, timeout_seconds=5).value == 3
    assert second_client.models.calls == 0


def test_invalid_json_is_retried_once_then_fails_safely() -> None:
    provider, client = _provider(["not json", "still not json"])
    with pytest.raises(LLMProviderError) as info:
        provider.generate_structured(prompt="secret prompt text", schema=Answer, timeout_seconds=5)
    assert client.models.calls == 2
    assert "secret prompt text" not in str(info.value)


def test_retry_recovers_when_second_answer_is_valid() -> None:
    provider, client = _provider(["not json", '{"value": 1}'])
    assert provider.generate_structured(prompt="p", schema=Answer, timeout_seconds=5).value == 1
    assert client.models.calls == 2


def test_model_name_is_required() -> None:
    with pytest.raises(ValueError, match="LLM_MODEL"):
        GeminiProvider(api_key="x", model="", client=FakeClient([]))  # type: ignore[arg-type]


def test_file_cache_rejects_non_hash_keys(tmp_path: Any) -> None:
    cache = FileCache(tmp_path)
    with pytest.raises(ValueError, match="SHA-256"):
        cache.get("../escape")


class FlakyModels:
    """Fails with a transient API error first, then answers. Counts every call."""

    def __init__(self, failures: int, text: str) -> None:
        self._failures = failures
        self._text = text
        self.calls = 0

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls += 1
        if self._failures > 0:
            self._failures -= 1
            raise APIError(
                503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}}
            )
        return SimpleNamespace(text=self._text)


def test_transient_api_error_is_retried_then_succeeds() -> None:
    client = SimpleNamespace(models=FlakyModels(failures=2, text='{"value": 5}'))
    provider = GeminiProvider(
        api_key="unused",
        model="test-model",
        client=client,  # type: ignore[arg-type]
        backoff_seconds=0,
    )
    assert provider.generate_structured(prompt="p", schema=Answer, timeout_seconds=5).value == 5
    assert client.models.calls == 3


def test_non_transient_api_error_fails_immediately() -> None:
    class Forbidden(FlakyModels):
        def generate_content(self, **kwargs: Any) -> Any:
            self.calls += 1
            raise APIError(
                403, {"error": {"code": 403, "message": "denied", "status": "PERMISSION_DENIED"}}
            )

    client = SimpleNamespace(models=Forbidden(failures=0, text=""))
    provider = GeminiProvider(
        api_key="unused",
        model="test-model",
        client=client,  # type: ignore[arg-type]
        backoff_seconds=0,
    )
    with pytest.raises(LLMProviderError):
        provider.generate_structured(prompt="p", schema=Answer, timeout_seconds=5)
    assert client.models.calls == 1
