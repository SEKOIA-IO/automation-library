from pydantic import BaseModel, Field


class WithSecureModuleConfiguration(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    secret: str = Field(secret=True, description="API secret to authenticate")
