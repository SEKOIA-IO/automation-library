"""CrowdStrike Telemetry Module."""

from connectors import AwsModule
from pydantic.v1 import BaseModel, Field


class CrowdStrikeTelemetryModuleConfig(BaseModel):
    """Module Configuration."""

    aws_access_key: str = Field(alias="aws_access_key_id", description="The identifier of the access key")
    aws_secret_access_key: str = Field(
        secret=True, default=None, description="The secret associated to the access key"
    )
    aws_region_name: str = Field(alias="aws_region", description="The area hosting the AWS resources")


class CrowdStrikeTelemetryModule(AwsModule):
    """CrowdStrike Telemetry Module."""

    configuration: CrowdStrikeTelemetryModuleConfig
