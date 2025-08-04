from pydantic import BaseModel, Field


class BeyondTrustModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base URL")
    client_id: str = Field(..., description="Client ID")
    client_secret: str = Field(..., description="Client secret", secret=True)
