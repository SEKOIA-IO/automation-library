from pydantic import BaseModel, Field


class JumpcloudDirectoryInsightsModuleConfiguration(BaseModel):
    base_url: str = Field(
        "https://api.jumpcloud.com/",
        description="Jumpcloud Directory Insights API Base URL",
    )
    apikey: str = Field(
        json_schema_extra={"secret": True},
        description="The API key to authenticate calls to \
            the Jumpcloud Directory Insights API",
    )
