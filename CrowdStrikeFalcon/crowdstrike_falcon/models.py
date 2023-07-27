from pydantic import BaseModel, Field
from sekoia_automation.connector import DefaultConnectorConfiguration


class CrowdStrikeFalconModuleConfiguration(BaseModel):
    client_id: str = Field(..., description="OAuth2 Client Identifier as provided by CrowdStrike Falcon")
    client_secret: str = Field(secret=True, description="OAuth2 Client Secret as provided by CrowdStrike Falcon")
    base_url: str = Field(..., description="Base URL of the CrowdStrike Falcon platform")


class CrowdStrikeFalconEventStreamConfiguration(DefaultConnectorConfiguration):
    tg_base_url: str = Field(None, description="Base URL of the ThreatGraphAPI")
    tg_username: str | None = Field(None, description="The username for the ThreatGraphAPI")
    tg_password: str | None = Field(None, description="The password for the ThreatGraphAPI")
