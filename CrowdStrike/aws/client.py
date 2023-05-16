"""Aws base client wrapper with its config class."""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


class AwsConfiguration(BaseModel):
    """AWS client base configuration."""

    aws_access_key_id: str = Field(description="AWS access key id")
    aws_secret_access_key: str = Field(description="AWS secret access key")
    aws_region: str = Field(description="AWS region name")


AwsConfigurationT = TypeVar("AwsConfigurationT", bound=AwsConfiguration)


class AwsClient(Generic[AwsConfigurationT]):
    """
    Aws base client.

    All other clients should extend this base client.
    """

    _configuration: AwsConfigurationT

    def __init__(self, configuration: AwsConfigurationT) -> None:
        """
        Initialize AwsClient.

        Args:
            configuration: AwsConfigurationT
        """
        self._configuration: AwsConfigurationT = configuration
