"""Pydantic models for Okta device API responses."""

from typing import Any, Optional

from pydantic import BaseModel, Field

__all__ = [
    "OktaDevice",
    "OktaDeviceDisplayName",
    "OktaDeviceEmbeddedResources",
    "OktaDeviceLink",
    "OktaDeviceLinkHints",
    "OktaDeviceProfile",
]


class OktaDeviceDisplayName(BaseModel):
    """Display name metadata returned by the Okta device API."""

    value: str
    sensitive: bool


class OktaDeviceLinkHints(BaseModel):
    """HTTP method hints attached to an Okta device link."""

    allow: list[str]


class OktaDeviceLink(BaseModel):
    """Hypermedia link returned by the Okta device API."""

    href: str
    hints: OktaDeviceLinkHints


class OktaDeviceEmbeddedResources(BaseModel):
    """Embedded resources returned with an Okta device payload."""

    users: list[dict[str, Any]] = Field(default_factory=list)


class OktaDeviceProfile(BaseModel):
    """Okta device profile."""

    displayName: str
    platform: str
    registered: bool
    secureHardwarePresent: bool
    osVersion: Optional[str] = None
    serialNumber: Optional[str] = None
    sid: Optional[str] = None
    diskEncryptionType: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    imei: Optional[str] = None
    udid: Optional[str] = None


class OktaDevice(BaseModel):
    """Okta device."""

    id: str
    status: str
    created: str
    lastUpdated: str
    lastSeen: Optional[str] = None
    profile: OktaDeviceProfile
    resourceType: Optional[str] = None
    resourceDisplayName: Optional[OktaDeviceDisplayName] = None
    resourceAlternateId: Optional[str] = None
    resourceId: Optional[str] = None
    links: Optional[dict[str, OktaDeviceLink]] = Field(default=None, alias="_links")
    embedded: Optional[OktaDeviceEmbeddedResources] = Field(default=None, alias="_embedded")
