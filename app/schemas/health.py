from typing import Literal

from pydantic import BaseModel, ConfigDict


class LivenessResponse(BaseModel):
    """The process is running. Does not check dependencies."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    """The service can handle traffic. Returned with HTTP 200 only when the database is reachable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ready"]
    database: Literal["ok"]
