from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class HarfanglabAssetConnectorModuleConfiguration(BaseModel):
    api_key: str = Field(..., description="API key for Harfanglab Asset Connector")
    base_url: str = Field(..., description="Base URL for the Harfanglab Asset Connector API")


class HarfanglabAssetConnectorModule(Module):
    configuration: HarfanglabAssetConnectorModuleConfiguration
