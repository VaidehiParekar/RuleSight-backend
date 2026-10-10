from typing import Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProviderError(Exception):
    """Raised when a provider call fails, times out, or returns output that is not valid JSON.

    The message is safe to log. It must not contain prompts, responses or API keys.
    """


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
