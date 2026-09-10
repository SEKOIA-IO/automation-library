from pydantic import BaseModel, Field
from sekoia_automation.connector import Connector
from sekoia_automation.module import Module


class SophosConfiguration(BaseModel):
    oauth2_authorization_url: str = Field(..., description="The url to the OAuth2 authorization")
    api_host: str = Field(
        ...,
        description="API Url of the Sophos Central API (e.g. 'https://api-{dataRegion}.central.sophos.com')",
    )
    client_id: str = Field(..., description="OAuth2 client identifier")
    client_secret: str = Field(secret=True, description="OAuth2 client secret")


class SophosModule(Module):
    configuration: SophosConfiguration


class SophosConnector(Connector):
    module: SophosModule
