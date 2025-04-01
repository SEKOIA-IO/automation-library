from abc import ABCMeta
from functools import cached_property

import boto3
from pydantic.v1 import BaseModel, Field
from sekoia_automation.connector import Connector
from sekoia_automation.module import Module


class AWSConfiguration(BaseModel):
    aws_access_key: str = Field(..., description="The identifier of the access key")
    aws_secret_access_key: str = Field(secret=True, description="The secret associated to the access key")
    aws_region_name: str = Field(..., description="The area hosting the AWS resources")


class AWSModule(Module):
    configuration: AWSConfiguration


class AWSConnector(Connector, metaclass=ABCMeta):
    module: AWSModule

    def new_session(self) -> boto3.Session:
        return boto3.Session(
            aws_access_key_id=self.module.configuration.aws_access_key,
            aws_secret_access_key=self.module.configuration.aws_secret_access_key,
            region_name=self.module.configuration.aws_region_name,
        )

    @cached_property
    def session(self) -> boto3.Session:
        return self.new_session()
