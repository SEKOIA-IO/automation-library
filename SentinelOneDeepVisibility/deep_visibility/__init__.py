from pydantic.v1 import BaseModel, Field
from sekoia_automation.connector import Connector
from sekoia_automation.module import Module


class SentinelOneDeepVisibilityConfiguration(BaseModel):
    aws_access_key: str = Field(..., description="The identifier of the access key")
    aws_secret_access_key: str = Field(secret=True, description="The secret associated to the access key")
    aws_region_name: str = Field(..., description="The area hosting the AWS resources")


class SentinelOneDeepVisibilityModule(Module):
    configuration: SentinelOneDeepVisibilityConfiguration


class SentinelOneDeepVisibilityConnector(Connector):
    module: SentinelOneDeepVisibilityModule
