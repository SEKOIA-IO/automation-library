from pydantic import BaseModel, Field
from sekoia_automation.connector import Connector
from sekoia_automation.module import Module


class SentinelOneDeepVisibilityConfiguration(BaseModel):
    aws_role_arn: str | None = Field(default=None, description="The ARN of the AWS role to assume")
    aws_access_key: str | None = Field(default=None, description="The identifier of the access key")
    aws_secret_access_key: str | None = Field(
        default=None, description="The secret associated to the access key", json_schema_extra={"secret": True}
    )
    aws_region_name: str = Field(..., description="The area hosting the AWS resources")


class SentinelOneDeepVisibilityModule(Module):
    configuration: SentinelOneDeepVisibilityConfiguration


class SentinelOneDeepVisibilityConnector(Connector):
    module: SentinelOneDeepVisibilityModule
