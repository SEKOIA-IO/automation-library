from pydantic import BaseModel, Field
from sekoia_automation.connector import Connector
from sekoia_automation.module import Module


class LaceworkConfiguration(BaseModel):
    secret: str = Field(..., description="The secret of your API Key", secret=True)
    key_id: str = Field(..., description="The KeyId of your API Key")
    account: str = Field(..., description="The account of your API Key (e.g: `YourLaceworkTenant.lacework.net`)")


class LaceworkModule(Module):
    configuration: LaceworkConfiguration


class LaceworkConnector(Connector):
    module: LaceworkModule
