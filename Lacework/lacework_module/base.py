from pydantic import BaseModel, Field
from sekoia_automation.connector import Connector
from sekoia_automation.module import Module


class LaceworkConfiguration(BaseModel):
    secret_key: str = Field(secret=True, description="Your unique identifier used as the Authorization header")
    access_key: str = Field(..., description="Your unique key to create the token used to authenticate the API Key.")
    lacework_url: str = Field(..., description="Your Lacework application name")


class LaceworkModule(Module):
    configuration: LaceworkConfiguration


class LaceworkConnector(Connector):
    module: LaceworkModule