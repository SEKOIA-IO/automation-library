from pydantic import BaseModel, Field


class ThinkstCanaryModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base URL")
    auth_token: str = Field(secret=True, description="Auth token")
