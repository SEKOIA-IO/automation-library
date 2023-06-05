"""
Models for investigation attributes.

https://developer.manage.trellix.com/mvision/apis/investigations
"""
from datetime import datetime

from pydantic import BaseModel


class InvestigationAttributes(BaseModel):
    """Model for investigation attributes."""

    tenantId: str
    name: str
    summary: str
    owner: str
    created: datetime
    lastModified: datetime
    source: str
    isAutomatic: bool
    investigated: bool
    hint: str
    caseType: str
    status: str
    priority: str
