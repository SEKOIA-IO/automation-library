from pydantic import Field

from asset_connector.models import DefaultAssetConnectorConfiguration


class HarfanglabAssetConnectorConfiguration(DefaultAssetConnectorConfiguration):
    harfanglab_api_key: str = Field(..., description="API key for Harfanglab Asset Connector")
    harfanglab_base_url: str = Field(..., description="Base URL for the Harfanglab Asset Connector API")
