"""
Models for EDR Alerts attributes.

https://developer.manage.trellix.com/mvision/apis/threats
"""

from pydantic import BaseModel


class EdrAlertAttributes(BaseModel):
    """Alert Attributes."""

    traceId: str
    parentTraceId: str
    rootTraceId: str | None = None
    aGuid: str
    detectionDate: str | None = None
    eventDate: str | None = None
    eventType: str
    severity: str | None = None
    score: int | None = None
    detectionTags: list[str] | None = None
    relatedTraceIds: list[str] | None = None
    ruleId: str | None = None
    rank: int | None = None
    pid: int | None = None
    version: str | None = None
    parentsTraceId: list[str] | None = None
    processName: str | None = None
    user: str | None = None
    cmdLine: str | None = None
    hashId: str | None = None
    h_os: str | None = None
    domain: str | None = None
    hostName: str | None = None
