from pydantic.v1 import BaseModel, Field


class NewRelicModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base URL")
    api_key: str = Field(..., description="API key", secret=True)
