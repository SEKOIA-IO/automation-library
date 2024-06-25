from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class BitsightModuleConfiguration(BaseModel):
    """Contains all necessary configuration to interact with Bitsight API."""

    api_token: str = Field(
        required=True, secret=True, description="The API token to authenticate call to the Bitsight API"
    )

    company_uuids: list[str] = Field(required=True, description="The company uuids to fetch data from Bitsight API")


class BitsightModule(Module):
    """Configuration for Bitsight module."""

    configuration: BitsightModuleConfiguration
