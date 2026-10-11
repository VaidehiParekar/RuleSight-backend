import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, ValidationError

from app.integrations.llm.base import LLMProviderError, SchemaT, Usage
from app.integrations.llm.cache import FileCache, LLMCache, MemoryCache

logger = logging.getLogger("app.llm.gemini")

# Bump when prompts or schemas change in a way that makes old cached answers invalid.
CACHE_VERSION = "1"
# One retry when the model returns JSON that fails schema validation.
MAX_ATTEMPTS = 2
# Retries for transient API failures: rate limit, internal error, overload, gateway timeout.
MAX_TRANSPORT_ATTEMPTS = 3
TRANSIENT_CODES = frozenset({429, 500, 503, 504})
_RETRY_IN = re.compile(r"retry in (\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


class GeminiProvider:
    """Structured-output adapter for the Gemini API (google-genai SDK).

    Every call uses temperature 0 and a JSON response schema. Answers are cached by a hash of
    (model, schema, prompt), so reruns return the same result and do not spend free-tier quota.
    Errors are logged without prompts, responses or keys.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        cache: LLMCache | None = None,
        client: genai.Client | None = None,
        backoff_seconds: float = 2.0,
        transport_attempts: int = MAX_TRANSPORT_ATTEMPTS,
        timeout_seconds: float | None = None,
        min_interval_seconds: float = 0.0,
    ) -> None:
        if not model:
            raise ValueError("a Gemini model name is required (set LLM_MODEL)")
        self._model = model
        self._cache: LLMCache = cache or MemoryCache()
        self._client = client or genai.Client(api_key=api_key)
        self._backoff_seconds = backoff_seconds
        self._transport_attempts = max(1, transport_attempts)
        # When set, overrides the per-step timeout: long regulations need longer calls.
        self._timeout_seconds = timeout_seconds
        self._min_interval_seconds = min_interval_seconds
        self._last_call = float("-inf")
        self._cache_hits = 0
        self._input_tokens = 0
        self._output_tokens = 0

    def usage(self) -> Usage:
        """Running totals since the provider was built: cache hits and tokens billed."""
        return Usage(self._cache_hits, self._input_tokens, self._output_tokens)

    def _cache_key(self, prompt: str, schema: type[BaseModel]) -> str:
        material = "\n".join(
            [CACHE_VERSION, self._model, f"{schema.__module__}.{schema.__qualname__}", prompt]
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _config(
        self, schema: type[BaseModel], timeout_seconds: float
    ) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=schema,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )

    def _pace(self) -> None:
        """Keeps calls at least min_interval apart, so bursts do not hit per-minute limits."""
        wait = self._min_interval_seconds - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _generate(self, prompt: str, schema: type[BaseModel], timeout_seconds: float) -> Any:
        """Calls the API, retrying transient failures (rate limit, overload) with backoff."""
        for transport_attempt in range(1, self._transport_attempts + 1):
            try:
                self._pace()
                return self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=self._config(schema, timeout_seconds),
                )
            except APIError as exc:
                transient = exc.code in TRANSIENT_CODES
                if transient and transport_attempt < self._transport_attempts:
                    logger.warning(
                        "transient gemini error, retrying",
                        extra={"code": exc.code, "attempt": transport_attempt},
                    )
                    backoff = self._backoff_seconds * 2 ** (transport_attempt - 1)
                    # A rate-limit answer says how long to wait ("retry in 37.2s"); honour it.
                    asked = _RETRY_IN.search(str(exc))
                    time.sleep(max(backoff, float(asked.group(1)) + 1) if asked else backoff)
                    continue
                logger.error("gemini request failed", extra={"code": exc.code})
                raise LLMProviderError("The language model request failed.") from None
            except Exception as exc:
                # Log the exception type only. The message can echo request details.
                logger.error("gemini request failed", extra={"error_type": type(exc).__name__})
                raise LLMProviderError("The language model request failed.") from None
        raise LLMProviderError("The language model request failed.")

    def generate_structured(
        self,
        *,
        prompt: str,
        schema: type[SchemaT],
        timeout_seconds: float,
    ) -> SchemaT:
        key = self._cache_key(prompt, schema)
        cached = self._cache.get(key)
        if cached is not None:
            try:
                parsed_cached = schema.model_validate_json(cached)
                self._cache_hits += 1
                return parsed_cached
            except ValidationError:
                # A stale or corrupt entry is ignored and replaced by a fresh call.
                logger.warning("ignoring unreadable cache entry", extra={"schema": schema.__name__})

        for attempt in range(1, MAX_ATTEMPTS + 1):
            response = self._generate(prompt, schema, self._timeout_seconds or timeout_seconds)
            metadata = getattr(response, "usage_metadata", None)
            if metadata is not None:
                self._input_tokens += metadata.prompt_token_count or 0
                self._output_tokens += metadata.candidates_token_count or 0

            raw: str = response.text or ""
            try:
                parsed = schema.model_validate_json(raw)
            except ValidationError:
                logger.warning(
                    "model output failed schema validation",
                    extra={"schema": schema.__name__, "attempt": attempt},
                )
                continue
            self._cache.put(key, parsed.model_dump_json())
            return parsed

        raise LLMProviderError("The language model returned output that did not match the schema.")


def build_gemini_provider(
    *,
    api_key: str,
    model: str,
    cache_dir: Path | None,
    transport_attempts: int = MAX_TRANSPORT_ATTEMPTS,
    backoff_seconds: float = 2.0,
    timeout_seconds: float | None = None,
    min_interval_seconds: float = 0.0,
) -> GeminiProvider:
    """Builds the provider from settings. A file cache is used only when cache_dir is set."""
    cache: LLMCache = FileCache(cache_dir) if cache_dir is not None else MemoryCache()
    return GeminiProvider(
        api_key=api_key,
        model=model,
        cache=cache,
        transport_attempts=transport_attempts,
        backoff_seconds=backoff_seconds,
        timeout_seconds=timeout_seconds,
        min_interval_seconds=min_interval_seconds,
    )
