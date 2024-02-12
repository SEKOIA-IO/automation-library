from pydantic import BaseModel, Field


class ExtraHopModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="API base URL")
    client_id: str = Field(..., description="Client ID")
    client_secret: str = Field(secret=True, description="Client Secret")
