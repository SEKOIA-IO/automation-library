from pydantic import BaseModel, Field
from sekoia_automation.connector import Connector
from sekoia_automation.module import Module


class CortexConfiguration(BaseModel):
    api_key: str = Field(..., description="The API Key is your unique identifier used as the Authorization header")
    api_key_id: str = Field(..., description="The API Key ID is your unique token used to authenticate the API Key.")
    fqdn: str = Field(..., description="Unique host and domain name associated with each tenant")


class CortexModule(Module):
    configuration: CortexConfiguration


class CortexConnector(Connector):
    module: CortexModule
