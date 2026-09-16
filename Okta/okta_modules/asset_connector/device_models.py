"""Pydantic models for Okta device API responses."""

from typing import Any

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

    allow: list[str] | None = None


class OktaDeviceLink(BaseModel):
    """Hypermedia link returned by the Okta device API."""

    href: str
    hints: OktaDeviceLinkHints | None = None


class OktaDeviceEmbeddedResources(BaseModel):
    """Embedded resources returned with an Okta device payload."""

    users: list[dict[str, Any]] = Field(default_factory=list)


class OktaDeviceProfile(BaseModel):
    """Okta device profile."""

    displayName: str
    platform: str
    registered: bool
    secureHardwarePresent: bool
    osVersion: str | None = None
    serialNumber: str | None = None
    sid: str | None = None
    diskEncryptionType: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    imei: str | None = None
    udid: str | None = None


class OktaDevice(BaseModel):
    """Okta device."""

    id: str
    status: str
    created: str
    lastUpdated: str
    lastSeen: str | None = None
    profile: OktaDeviceProfile
    resourceType: str | None = None
    resourceDisplayName: OktaDeviceDisplayName | None = None
    resourceAlternateId: str | None = None
    resourceId: str | None = None
    links: dict[str, OktaDeviceLink | list[OktaDeviceLink]] | None = Field(default=None, alias="_links")
    embedded: OktaDeviceEmbeddedResources | None = Field(default=None, alias="_embedded")
