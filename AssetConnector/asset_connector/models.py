from pydantic import BaseModel

# from enum import Enum
from typing import Literal


class DefaultAssetConnectorConfiguration(BaseModel):
    sekoia_base_url: str | None
    api_key: str
    frequency: int = 60


class Metadata(BaseModel):
    product: str
    version: str


class User(BaseModel):
    has_mfa: bool
    name: str
    uid: int
    groups: list[str]
    full_name: str
    email_addr: str


class GeoLocation(BaseModel):
    city: str | None = None
    country: str | None = None


class OperatingSystem(BaseModel):
    name: str | None = None
    type: str | None = None
    type_id: int | None = None


class Device(BaseModel):
    type_id: int
    type: str
    uid: str
    location: GeoLocation | None = None
    os: OperatingSystem | None = None
    hostname: str


class EncryptionObject(BaseModel):
    partitions: dict[str, Literal["Disabled", "Enabled"]]


class DataObject(BaseModel):
    Firewall_status: Literal["Disabled", "Enabled"] | None = None
    Storage_encryption: EncryptionObject | None = None


class EnrichementObject(BaseModel):
    name: str
    value: str
    data: DataObject


class Enrichement(BaseModel):
    Enrichements: list[EnrichementObject] | None = None


class OCSFBaseModel(BaseModel):
    activity_id: int
    activity_name: str
    category_name: str
    category_uid: int
    class_name: str
    class_uid: int
    type_name: str
    type_uid: int
    severity: Literal["Unknown", "Informational", "Low", "Medium", "High", "Critical", "Fatal", "Other"] | None = None
    severity_id: int | None = None
    time: float
    metadata: Metadata


# TO DO: Implement the VulnerabilityOCSFModel according to OCSF specifications
class VulnerabilityOCSFModel(BaseModel):
    pass


class DeviceOCSFModel(OCSFBaseModel):
    device: Device
    enrichments: Enrichement | None = None


class UserOCSFModel(OCSFBaseModel):
    user: User


# TO DO: Implement the SoftwareOCSFModel according to OCSF specifications
class SoftwareOCSFModel(BaseModel):
    pass


# This model to be delete it after the migration to OCSF
# It is used to be compatible with the fake asset connector
class AssetObject(BaseModel):
    name: str
    type: Literal["host", "account"]


class AssetList(BaseModel):
    version: int  # Version of the our OCSF schema
    items: list[VulnerabilityOCSFModel | DeviceOCSFModel | UserOCSFModel | SoftwareOCSFModel | AssetObject] = []
