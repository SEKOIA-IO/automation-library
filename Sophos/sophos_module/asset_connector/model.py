"""
Pydantic models for Sophos Central API endpoint responses.
Reference: GET /endpoint/v1/endpoints
"""

from pydantic import BaseModel, Field


class SophosTenant(BaseModel):
    id: str | None = None


class SophosHealthServices(BaseModel):
    status: str | None = None
    serviceDetails: list[dict[str, str]] | None = None


class SophosHealth(BaseModel):
    overall: str | None = None
    threats: dict[str, str] | None = None
    services: SophosHealthServices | None = None


class SophosOS(BaseModel):
    isServer: bool | None = None
    platform: str | None = None
    name: str | None = None
    majorVersion: int | None = None
    minorVersion: int | None = None
    build: int | None = None


class SophosAssociatedPerson(BaseModel):
    name: str | None = None
    viaLogin: str | None = None
    id: str | None = None


class SophosAssignedProduct(BaseModel):
    code: str | None = None
    version: str | None = None
    status: str | None = None


class SophosPackageItem(BaseModel):
    assignedId: str | None = None
    name: str | None = None
    status: str | None = None
    available: list[dict[str, str]] | None = None


class SophosPackages(BaseModel):
    protection: SophosPackageItem | None = None
    ztna: SophosPackageItem | None = None
    encryption: SophosPackageItem | None = None


class SophosEncryptionVolume(BaseModel):
    volumeId: str | None = None
    status: str | None = None


class SophosEncryption(BaseModel):
    volumes: list[SophosEncryptionVolume] | None = None
    overallStatus: str | None = None


class SophosLockdown(BaseModel):
    status: str | None = None


class SophosCloud(BaseModel):
    provider: str | None = None
    instanceId: str | None = None


class SophosIsolation(BaseModel):
    status: str | None = None
    adminIsolated: bool | None = None
    selfIsolated: bool | None = None


class SophosModule_(BaseModel):
    name: str | None = None
    version: str | None = None


class SophosGroup(BaseModel):
    id: str | None = None
    name: str | None = None


class SophosEndpoint(BaseModel):
    id: str | None = None
    type: str | None = None
    tenant: SophosTenant | None = None
    hostname: str | None = None
    health: SophosHealth | None = None
    os: SophosOS | None = None
    ipv4Addresses: list[str] = Field(default_factory=list)
    ipv6Addresses: list[str] = Field(default_factory=list)
    macAddresses: list[str] = Field(default_factory=list)
    mdrManaged: bool | None = None
    associatedPerson: SophosAssociatedPerson | None = None
    tamperProtectionSupported: bool | None = None
    tamperProtectionEnabled: bool | None = None
    assignedProducts: list[SophosAssignedProduct] = Field(default_factory=list)
    packages: SophosPackages | None = None
    deviceSoftware: SophosPackages | None = None
    lastSeenAt: str | None = None
    encryption: SophosEncryption | None = None
    lockdown: SophosLockdown | None = None
    tags: list[str] = Field(default_factory=list)
    online: bool | None = None
    cloud: SophosCloud | None = None
    isolation: SophosIsolation | None = None
    modules: list[SophosModule_] = Field(default_factory=list)
    registeredAt: str | None = None
    group: SophosGroup | None = None


class SophosPages(BaseModel):
    size: int | None = None
    maxSize: int | None = None
    nextKey: str | None = None


class SophosEndpointsResponse(BaseModel):
    items: list[SophosEndpoint] = Field(default_factory=list)
    pages: SophosPages | None = None
