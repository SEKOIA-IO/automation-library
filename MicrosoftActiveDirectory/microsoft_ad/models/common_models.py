from pydantic.v1 import BaseModel, Field

from sekoia_automation.module import Module
from sekoia_automation.asset_connector.models.connector import DefaultAssetConnectorConfiguration


class MicrosoftADConfiguration(BaseModel):
    servername: str = Field(..., description="Remote machine IP or Name")
    admin_username: str = Field(..., description="Admin username")
    admin_password: str = Field(..., secret=True, description="Admin password")  # type: ignore
    ca_certificate: str | None = Field(None, description="PEM-encoded CA certificate for TLS verification")


class MicrosoftADModule(Module):
    configuration: MicrosoftADConfiguration


class MicrosoftADConnectorConfiguration(DefaultAssetConnectorConfiguration):
    basedn: str | None = Field(None, description="Active directory basedn")
