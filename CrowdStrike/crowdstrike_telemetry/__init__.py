"""CrowdStrike Telemetry Module."""

from connectors import AwsModule
from pydantic import BaseModel, Field


class CrowdStrikeTelemetryModuleConfig(BaseModel):
    """Module Configuration."""

    aws_role_arn: str | None = Field(default=None, description="The ARN of the AWS role to assume")
    aws_access_key: str = Field(alias="aws_access_key_id", description="The identifier of the access key")
    aws_secret_access_key: str = Field(
        default=..., json_schema_extra={"secret": True}, description="The secret associated to the access key"
    )
    aws_region_name: str = Field(alias="aws_region", description="The area hosting the AWS resources")


class CrowdStrikeTelemetryModule(AwsModule):
    """CrowdStrike Telemetry Module."""

    configuration: CrowdStrikeTelemetryModuleConfig
