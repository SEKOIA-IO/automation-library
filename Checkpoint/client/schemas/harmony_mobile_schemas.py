from datetime import datetime

from pydantic import BaseModel


class HarmonyMobileSchema(BaseModel):
    """
    Model that represent Harmony Mobile Result schema.

    More information is here:
    https://app.swaggerhub.com/apis-docs/Check-Point/harmony-mobile/ then search for "Get /external_api/v3/alerts"
    """

    id: int
    device_rooted: bool
    attack_vector: str
    details: str
    device_id: str | int  # A string according to the openapi spec, but an integer according to the API response
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
