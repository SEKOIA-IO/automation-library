from pydantic import BaseModel, Field


class MicrosoftDefenderModuleConfiguration(BaseModel):
    base_url: str = Field("https://api.securitycenter.microsoft.com", description="Base URL")
    app_id: str = Field(..., description="App ID")
    app_secret: str = Field(..., description="App Secret", secret=True)
    tenant_id: str = Field(..., description="Tenant ID")
