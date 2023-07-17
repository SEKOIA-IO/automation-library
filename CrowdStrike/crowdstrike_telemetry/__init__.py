"""CrowdStrike Telemetry Module."""

from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class CrowdStrikeTelemetryModuleConfig(BaseModel):
    """Module Configuration."""

    aws_secret_access_key: str = Field(secret=True)
    aws_access_key_id: str
    aws_region: str


class CrowdStrikeTelemetryModule(Module):
    """CrowdStrikeTelemetryModule."""

    configuration: CrowdStrikeTelemetryModuleConfig
