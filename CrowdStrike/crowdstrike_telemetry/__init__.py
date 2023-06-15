"""CrowdStrike Telemetry Module."""

from pydantic import BaseModel
from sekoia_automation.module import Module


class CrowdStrikeTelemetryModuleConfig(BaseModel):
    """Module Configuration."""

    aws_secret_access_key: str
    aws_access_key_id: str
    aws_region: str


class CrowdStrikeTelemetryModule(Module):
    """CrowdStrikeTelemetryModule."""

    configuration: CrowdStrikeTelemetryModuleConfig
