from pydantic.v1 import BaseModel, Field
from sekoia_automation.module import Module


class DelineaModuleConfiguration(BaseModel):
    client_id: str = Field(..., description="Client Id to interact with the API")
    client_secret: str = Field(..., secret=True, description="Client Secret to interact with the API")
    base_url: str = Field(..., description="The base URL of the Delinea instance")


class DelineaModule(Module):
    configuration: DelineaModuleConfiguration
