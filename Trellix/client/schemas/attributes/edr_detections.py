"""
Models for EDR Threat Detections attributes.

https://developer.manage.trellix.com/mvision/apis/threats
"""

from typing import Any

from pydantic import BaseModel


class EdrDetectionAttributes(BaseModel):
    """Detection Attributes."""

    traceId: str
    firstDetected: str
    severity: str
    rank: int
    tags: list[str] | None = None
    host: dict[str, Any] | None = None
    sha256: str
