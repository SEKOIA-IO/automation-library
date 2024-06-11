from sekoia_automation.module import Module
from sekoia_automation.action import Action
from pydantic import BaseModel, Field, HttpUrl


class NybbleConfiguration(BaseModel):
    nhub_url: HttpUrl = Field(..., description="Nybble Hub Connector Base URL")
    nhub_username: str = Field(..., description="Nybble Hub Connector username")
    nhub_key: str = Field(secret=True, description="Nybble Hub Connector Key to authenticate the requests")


class NybbleModule(Module):
    configuration: NybbleConfiguration


class NybbleAction(Action):
    module: NybbleModule
