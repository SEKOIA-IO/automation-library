"""Package for the Vectra module and connectors."""

from pydantic.v1 import BaseModel, Field
from sekoia_automation.module import Module


class VectraModuleConfiguration(BaseModel):
    base_url: str = Field(
        description="Base url to interact with Vectra API",
    )
    client_id: str = Field(..., description="Client Id to interact with Vectra API")
    client_secret: str = Field(secret=True, description="Secret key to work with Vectra API")


class VectraModule(Module):
    configuration: VectraModuleConfiguration
