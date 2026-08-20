from datetime import UTC, datetime
from typing import Any

from dateutil.parser import isoparse
from pydantic import BaseModel, Field
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.module import Module


class UpwindModuleConfig(BaseModel):
    base_url: str = Field(default="https://api.upwind.io", description="Base URL of the Upwind API")
    auth_url: str = Field(
        default="https://auth.upwind.io/oauth/token",
        description="OAuth2 token endpoint",
    )
    client_id: str = Field(..., description="OAuth2 client ID")
    client_secret: str = Field(..., description="OAuth2 client secret", json_schema_extra={"secret": True})
    organization_id: str = Field(..., description="Upwind organization ID")


class UpwindModule(Module):
    configuration: UpwindModuleConfig


class UpwindConnectorConfig(DefaultConnectorConfiguration):
    frequency: int = Field(default=60, ge=1)


def _parse_upwind_datetime(raw_value: Any) -> datetime | None:
    if not raw_value:
        return None

    try:
        parsed = isoparse(str(raw_value))
    except Exception:
        return None

    if not isinstance(parsed, datetime):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def extract_upwind_detection_datetime(event: dict[str, Any]) -> datetime | None:
    for field_name in ("last_seen_time", "first_seen_time"):
        parsed = _parse_upwind_datetime(event.get(field_name))
        if parsed is not None:
            return parsed

    return None
