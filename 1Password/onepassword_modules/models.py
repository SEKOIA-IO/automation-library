from pydantic import BaseModel, Field


class OnePasswordModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base URL")
    api_token: str = Field(..., description="API token", secret=True)
