from pydantic import BaseModel, Field


class DuoModuleConfiguration(BaseModel):
    hostname: str = Field(..., description="API hostname")
    integration_key: str = Field(..., description="Admin API integration key")
    secret_key: str = Field(secret=True, description="Integration secret key")
