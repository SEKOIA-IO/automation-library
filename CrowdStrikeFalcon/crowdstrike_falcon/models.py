from pydantic import BaseModel, Field


class CrowdStrikeFalconModuleConfiguration(BaseModel):
    client_id: str = Field(..., description="OAuth2 Client Identifier as provided by CrowdStrike Falcon")
    client_secret: str = Field(secret=True, description="OAuth2 Client Secret as provided by CrowdStrike Falcon")
    base_url: str = Field(..., description="Base URL of the CrowdStrike Falcon platform")
