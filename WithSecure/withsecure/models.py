from pydantic import BaseModel, Field


class WithSecureModuleConfiguration(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    secret: str = Field(..., description="API secret to authenticate")
