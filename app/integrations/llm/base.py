from typing import NamedTuple, Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProviderError(Exception):
    """Raised when a provider call fails, times out, or returns output that is not valid JSON.

    The message is safe to log. It must not contain prompts, responses or API keys.
    """


class Usage(NamedTuple):
    """Running totals a provider may report. Fakes and providers without metering report zero."""

    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def __sub__(self, other: "Usage") -> "Usage":  # type: ignore[override]
        return Usage(*(a - b for a, b in zip(self, other, strict=True)))


def usage_of(provider: object) -> Usage:
    """The provider's usage totals, or zeros when it does not meter calls."""
    meter = getattr(provider, "usage", None)
    return meter() if callable(meter) else Usage()


class StructuredLLMProvider(Protocol):
    """Contract for any language model used by the application.

    Implementations must return output that validates against ``schema``. Callers still apply
    business-rule validation, because a schema match alone does not make a result correct.
    """

    def generate_structured(
        self,
        *,
        prompt: str,
        schema: type[SchemaT],
        timeout_seconds: float,
    ) -> SchemaT:
        """Returns a validated ``schema`` instance or raises LLMProviderError."""
        ...
