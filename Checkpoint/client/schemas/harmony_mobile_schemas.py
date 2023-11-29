from datetime import datetime

from pydantic import BaseModel


class HarmonyMobileSchema(BaseModel):
    """
    Model that represent Harmony Mobile Result schema.

    More information is here:
    https://app.swaggerhub.com/apis-docs/Check-Point/harmony-mobile/1.0.0-oas3#/Events/GetAlerts
    """

    id: int
    device_rooted: bool
    attack_vector: str
    details: str
    device_id: str
    email: str
    event: str
    mdm_uuid: str
    name: str
    number: str
    severity: str
    threat_factors: str
    device_model: str
    client_version: str
    backend_last_updated: datetime | None = None
    event_timestamp: datetime | None = None
