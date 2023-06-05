"""
Models for search attributes.

https://developer.manage.trellix.com/mvision/apis/searches
"""
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class SearchRealtimeAttributes(BaseModel):
    """Model for search realtime result attributes."""

    created: datetime
    HostInfo_hostname: str = Field(alias="HostInfo.hostname")
    HostInfo_ip_address: str = Field(alias="HostInfo.ip_address")
    HostInfo_os: str = Field(alias="HostInfo.os")
    HostInfo_connection_status: str = Field(alias="HostInfo.connection_status")
    HostInfo_platform: str = Field(alias="HostInfo.platform")
    BrowserHistory_url: str = Field(alias="BrowserHistory.url")
    BrowserHistory_title: str = Field(alias="BrowserHistory.title")
    BrowserHistory_last_visit_time: datetime = Field(alias="BrowserHistory.last_visit_time")
    BrowserHistory_visit_count: int = Field(alias="BrowserHistory.visit_count")
    BrowserHistory_visit_from: int = Field(alias="BrowserHistory.visit_from")
    BrowserHistory_browser: str = Field(alias="BrowserHistory.browser")
    BrowserHistory_user_profile: str = Field(alias="BrowserHistory.user_profile")
    BrowserHistory_browser_profile: str = Field(alias="BrowserHistory.browser_profile")
    BrowserHistory_url_length: int = Field(alias="BrowserHistory.url_length")
    BrowserHistory_hidden: int = Field(alias="BrowserHistory.hidden")
    BrowserHistory_typed_count: int = Field(alias="BrowserHistory.typed_count")


class SearchHistoricalAttributes(BaseModel):
    """Model for search historical attributes."""

    Maguid: str
    Logon_LogonType: str
    User_Domain: str
    Artifact: str
    Tags: List[str]
    DeviceName: str
    Activity: str
    RuleId: str
    DetectionDate: datetime
    Time: datetime
