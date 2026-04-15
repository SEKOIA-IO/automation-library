"""All available connectors for this module."""

from typing import Optional

from pydantic.v1 import BaseModel, Field
from sekoia_automation.module import Module


class AwsModuleConfiguration(BaseModel):
    """The configuration of the AWS module."""

    aws_role_arn: Optional[str] = Field(default=None, description="The ARN of the AWS role to assume")
    aws_access_key: Optional[str] = Field(default=None, description="The identifier of the access key")
    aws_secret_access_key: Optional[str] = Field(
        secret=True, default=None, description="The secret associated to the access key"
    )
    aws_region_name: str = Field(..., description="The area hosting the AWS resources")


class AwsModule(Module):
    """The AWS module."""

    configuration: AwsModuleConfiguration
