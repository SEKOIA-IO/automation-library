from typing import Optional

from pydantic.v1 import BaseModel, Field


class NozomiCaptureDevice(BaseModel):
    """A capture device entry attached to a Nozomi asset."""

    name: Optional[str] = None
    first_activity_time: Optional[str] = None
    last_activity_time: Optional[str] = None

    class Config:
        extra = "allow"


class NozomiAsset(BaseModel):
    """
    A single asset returned by the Guardian/CMC query API (``query=assets``).

    Only the identifier is required; every other field is optional so partial
    payloads from the API do not break parsing.
    """

    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    vendor: Optional[str] = None
    os: Optional[str] = None
    firmware_version: Optional[str] = None
    product_name: Optional[str] = None
    serial_number: Optional[str] = None
    device_id: Optional[str] = None
    ip: list[str] = Field(default_factory=list)
    mac_address: list[str] = Field(default_factory=list)
    mac_vendor: list[str] = Field(default_factory=list)
    vlan_id: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    levels: list[str] = Field(default_factory=list)
    zones: list[str] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)
    capture_devices: list[NozomiCaptureDevice] = Field(default_factory=list)
    created_at: Optional[str] = None
    last_activity_time: Optional[str] = None
    deleted_at: Optional[str] = None

    class Config:
        extra = "allow"


class NozomiAssetPage(BaseModel):
    """Envelope returned by the Guardian/CMC query API."""

    result: list[NozomiAsset] = Field(default_factory=list)
    total: Optional[int] = None

    class Config:
        extra = "allow"
