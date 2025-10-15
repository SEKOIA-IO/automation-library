"""CrowdStrike Telemetry Module."""

from connectors import AwsModule, AwsModuleConfiguration
from pydantic.v1 import Field


class CrowdStrikeTelemetryModuleConfig(AwsModuleConfiguration):
    """Module Configuration."""

    aws_access_key: str = Field(alias="aws_access_key_id", description="The identifier of the access key")
    aws_region_name: str = Field(alias="aws_region", description="The area hosting the AWS resources")


class CrowdStrikeTelemetryModule(AwsModule):
    """CrowdStrike Telemetry Module."""

    configuration: CrowdStrikeTelemetryModuleConfig
