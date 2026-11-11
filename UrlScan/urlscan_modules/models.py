from pydantic import BaseModel, Field


class UrlScanModuleConfiguration(BaseModel):
    api_key: str = Field(..., description="urlscan.io API key", json_schema_extra={"secret": True})
    base_url: str = "https://urlscan.io"
