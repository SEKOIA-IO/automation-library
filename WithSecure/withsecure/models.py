from pydantic import BaseModel, Field
from typing import Any


class WithSecureModuleConfiguration(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    secret: str = Field(secret=True, description="API secret to authenticate")


class RemoteOperationResponse(BaseModel):
    multistatus: list[Any]
    transactionId: str
