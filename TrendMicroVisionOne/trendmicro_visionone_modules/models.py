from pydantic.v1 import BaseModel, Field


class TrendMicroVisionOneModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base URL")
    api_key: str = Field(..., description="Trend Micro api_key", secret=True)
