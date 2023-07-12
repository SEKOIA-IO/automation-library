from functools import cached_property

from management.mgmtsdk_v2_1.mgmt import Management
from pydantic import BaseModel, Field
from sekoia_automation.action import Action
from sekoia_automation.module import Module


class SentinelOneConfiguration(BaseModel):
    hostname: str = Field(..., description="The url to the SentinelOne instance")
    api_token: str = Field(secret=True, description="The API token to authenticate the requests")


class SentinelOneModule(Module):
    configuration: SentinelOneConfiguration


class SentinelOneAction(Action):
    module: SentinelOneModule

    @cached_property
    def client(self):
        return Management(
            hostname=self.module.configuration.hostname,
            api_token=self.module.configuration.api_token,
        )
