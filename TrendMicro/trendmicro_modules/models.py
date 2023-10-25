from pydantic import BaseModel, Field


class TrendMicroModuleConfiguration(BaseModel):
    service_url: str = Field(..., description="Service URL")
    username: str = Field(..., description="Username")
    api_key: str = Field(..., description="API key", secret=True)
