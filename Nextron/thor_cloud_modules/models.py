from pydantic import BaseModel, Field


class ThorCloudModuleConfiguration(BaseModel):
    """Module-level configuration for THOR Cloud"""

    api_key: str = Field(
        ...,
        title="THOR Cloud API Key",
        description="API key for THOR Cloud or THOR Cloud Lite",
        json_schema_extra={"secret": True},
    )
