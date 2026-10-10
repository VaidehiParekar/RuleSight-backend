from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    """Describes one invalid input field. Contains the field path and a message, never the value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    message: str


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    request_id: str | None = None
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    """Single error envelope used by every non-2xx response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error: ErrorBody
