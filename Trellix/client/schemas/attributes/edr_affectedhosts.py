"""
Models for EDR Threat Affected Host attributes.

https://developer.manage.trellix.com/mvision/apis/threats
"""

from typing import Any

from pydantic import BaseModel


class EdrAffectedhostAttributes(BaseModel):
    """Affected Host Attributes."""

    detectionsCount: int
    severity: str
    rank: int
    firstDetected: str
    host: dict[str, Any]
