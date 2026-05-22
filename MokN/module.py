from pydantic.v1 import BaseModel, Field
from sekoia_automation.module import Module


class MoknModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base URL of the MokN tenant API")
    api_token: str = Field(
        ...,
        description="MokN API key used to authenticate against the tenant API",
        secret=True,
    )
    verify_ssl: bool = Field(
        True,
        description="Whether TLS certificates must be validated",
    )


class MoknModule(Module):
    configuration: MoknModuleConfiguration
