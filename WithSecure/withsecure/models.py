from typing import Any

from pydantic import BaseModel, Field


class WithSecureModuleConfiguration(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    secret: str = Field(..., description="API secret to authenticate", json_schema_extra={"secret": True})


class RemoteOperationResponse(BaseModel):
    multistatus: list[Any]
    transactionId: str


class ResponseActionResponse(BaseModel):
    id: str | None = None
