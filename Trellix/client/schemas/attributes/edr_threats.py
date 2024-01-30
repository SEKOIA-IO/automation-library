"""
Models for EDR Threat attributes.

https://developer.manage.trellix.com/mvision/apis/threats
"""

from typing import Any

from pydantic import BaseModel


class EdrThreatAttributes(BaseModel):
    """Threat Attributes."""

    aggregationKey: str
    severity: str
    rank: int
    score: int
    name: str
    type: str
    status: str
    firstDetected: str
    lastDetected: str
    hashes: dict[str, str]
    interpreter: dict[str, Any] | None = None
