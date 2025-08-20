from pydantic import Field

from asset_connector.models import DefaultAssetConnectorConfiguration


class EntraIDAssetConnectorConfiguration(DefaultAssetConnectorConfiguration):
    microsoft_token_url: str = Field(
        "https://login.microsoftonline.com",
        description="URL for Microsoft token endpoint"
    )
    microsoft_graph_api_base_url: str = Field(
        "https://graph.microsoft.com/v1.0", description="Base URL for Microsoft Graph API"
    )
    entra_id_tenant_id: str = Field(..., description="Tenant ID for Entra ID")
    entra_id_client_id: str = Field(..., description="Client ID for Entra ID")
    entra_id_client_secret: str = Field(..., description="Client Secret for Entra ID")
