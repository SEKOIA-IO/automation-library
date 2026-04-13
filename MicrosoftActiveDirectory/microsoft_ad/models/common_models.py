from pydantic.v1 import BaseModel, Field

from sekoia_automation.module import Module
from sekoia_automation.asset_connector.models.connector import (
    DefaultAssetConnectorConfiguration,
)


class MicrosoftADConfiguration(BaseModel):
    servername: str = Field(..., description="Remote machine IP or Name")
    admin_username: str = Field(..., description="Admin username")
    admin_password: str = Field(..., secret=True, description="Admin password")  # type: ignore
    ca_certificate: str | None = Field(None, secret=True, description="PEM-encoded CA certificate for TLS verification")  # type: ignore
    skip_tls_verify: bool = Field(
        False,
        description="Skip TLS certificate verification (insecure, use only for testing)",
    )
    port: int = Field(636, description="LDAPS port (default: 636)")
    tls_ciphers: str | None = Field(
        None,
        description="OpenSSL cipher string to force a specific cipher suite (e.g. 'AES256-GCM-SHA384'). Leave empty for automatic negotiation.",
    )


class MicrosoftADModule(Module):
    configuration: MicrosoftADConfiguration


class MicrosoftADConnectorConfiguration(DefaultAssetConnectorConfiguration):
    basedn: str | None = Field(None, description="Active directory basedn")
