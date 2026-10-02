from pydantic.v1 import BaseModel, Field
from sekoia_automation.module import Module


class StormshieldSNSConfiguration(BaseModel):
    url: str = Field(..., description="Base URL of the Stormshield SNS API")
    api_token: str = Field(..., secret=True, description="API token used to authenticate")  # type: ignore


class StormshieldSNSModule(Module):
    configuration: StormshieldSNSConfiguration
