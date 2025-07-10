from pydantic import BaseModel

from enum import Enum, IntEnum
from typing import Literal, Sequence, Union

from sekoia_automation.module import Module


# This class will be empty for the moment
# Because there is no defined module
class AssetConnectorModule(Module):
    """
    Base class for asset connector modules.
    """

    pass


class DefaultAssetConnectorConfiguration(BaseModel):
    """
    Base configuration for asset connectors.
    This configuration is used to define the basic parameters required for asset connectors.
    Attributes:
        sekoia_base_url (str | None): The base URL for the Sekoia.io API.
        api_key (str): The API key for authentication with the Sekoia.io API.
        frequency (int): The frequency in seconds at which the connector should run.
    """

    sekoia_base_url: str | None
    sekoia_api_key: str
    frequency: int = 60


## OCSF Models
class Product(BaseModel):
    """
    Product model for OCSF.
    https://schema.ocsf.io/1.5.0/objects/product
    attributes:
        name (str): The name of the product.
        vendor_name (str | None): The name of the vendor. Defaults to None.
        version (str | None): The version of the product.
    """

    name: str
    vendor_name: str | None = None
    version: str | None = None


class Metadata(BaseModel):
    """
    Metadata model for OCSF.
    """

    product: Product
    version: str


class OCSFBaseModel(BaseModel):
    """
    Base model for OCSF activities.
    This model includes common fields that are used in OCSF activities.
    """

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


### User Model
class Group(BaseModel):
    """
    Group model represents a user group.
    https://schema.ocsf.io/1.5.0/objects/group
    """

    name: str
    desc: str | None = None
    privileges: list[str] | None = None
    uid: str | None = None


class User(BaseModel):
    has_mfa: bool
    name: str
    uid: int
    groups: list[Group]
    full_name: str
    email_addr: str


class UserOCSFModel(OCSFBaseModel):
    """
    UserOCSFModel represents a user in the OCSF format.
    https://schema.ocsf.io/1.5.0/classes/user_inventory
    """

    user: User


### Device Model
class GeoLocation(BaseModel):
    """
    GeoLocation model represents the geographical location of a device.
    https://schema.ocsf.io/1.5.0/objects/location
    """

    city: str | None = None
    country: str | None = None


class OSTypeId(IntEnum):
    UNKNOWN = 0
    OTHER = 99
    WINDOWS = 100
    WINDOWS_MOBILE = 101
    LINUX = 200
    ANDROID = 201
    MACOS = 300
    IOS = 301
    IPADOS = 302
    SOLARIS = 400
    AIX = 401
    HPUX = 402


class OSTypeStr(Enum):
    UNKNOWN = "unknown"
    OTHER = "other"
    WINDOWS = "windows"
    WINDOWS_MOBILE = "windows mobile"
    LINUX = "linux"
    ANDROID = "android"
    MACOS = "macos"
    IOS = "ios"
    IPADOS = "ipados"
    SOLARIS = "solaris"
    AIX = "aix"
    HPUX = "hp-ux"


class OperatingSystem(BaseModel):
    """
    OperatingSystem model represents the operating system of a device.
    https://schema.ocsf.io/1.5.0/objects/os
    """

    name: str | None = None
    type: OSTypeStr | None = None
    type_id: OSTypeId | None = None


class DeviceTypeId(IntEnum):
    UNKNOWN = 0
    SERVER = 1
    DESKTOP = 2
    LAPTOP = 3
    TABLET = 4
    MOBILE = 5
    VIRTUAL = 6
    IOT = 7
    BROWSER = 8
    FIREWALL = 9
    SWITCH = 10
    HUB = 11
    ROUTER = 12
    IDS = 13
    IPS = 14
    LOAD_BALANCER = 15
    OTHER = 99


class DeviceTypeStr(Enum):
    UNKNOWN = "Unknown"
    SERVER = "Server"
    DESKTOP = "Desktop"
    LAPTOP = "Laptop"
    TABLET = "Tablet"
    MOBILE = "Mobile"
    VIRTUAL = "Virtual"
    IOT = "IOT"
    BROWSER = "Browser"
    FIREWALL = "Firewall"
    SWITCH = "Switch"
    HUB = "Hub"
    ROUTER = "Router"
    IDS = "IDS"
    IPS = "IPS"
    LOAD_BALANCER = "Load Balancer"
    OTHER = "Other"


class Device(BaseModel):
    """
    Device model represents a device object in the OCSF format.
    https://schema.ocsf.io/1.5.0/objects/device
    """

    type_id: DeviceTypeId
    type: DeviceTypeStr
    uid: str
    location: GeoLocation | None = None
    os: OperatingSystem | None = None
    hostname: str


class EncryptionObject(BaseModel):
    partitions: dict[str, Literal["Disabled", "Enabled"]]


class DataObject(BaseModel):
    """
    DataObject represents some data related to a device. ( Firewall and Storage encryption )
    """

    Firewall_status: Literal["Disabled", "Enabled"] | None = None
    Storage_encryption: EncryptionObject | None = None


class EnrichementObject(BaseModel):
    """
    Enrichement Object represents additional information about a device.
    """

    name: str
    value: str
    data: DataObject


class Enrichement(BaseModel):
    """
    List of enrichments for a device.
    """

    Enrichements: list[EnrichementObject] | None = None


class DeviceOCSFModel(OCSFBaseModel):
    """
    DeviceOCSFModel represents a device in the OCSF format.
    https://schema.ocsf.io/1.5.0/classes/inventory_info
    """

    device: Device
    enrichments: Enrichement | None = None


# TODO: Implement the SoftwareOCSFModel
# https://schema.ocsf.io/1.5.0/classes/software_info
class SoftwareOCSFModel(BaseModel):
    pass


### Vulnerability Model
class KillChainPhase(Enum):
    UNKOWN = "Unknown"
    RECONNAISSANCE = "Reconnaissance"
    WEAPONIZATION = "Weaponization"
    DELIVERY = "Delivery"
    EXPLOITATION = "Exploitation"
    INSTALLATION = "Installation"
    COMMAND_AND_CONTROL = "Command & Control"
    ACTIONS_ON_OBJECTIVES = "Actions on Objectives"
    OTHER = "Other"


class KillChainPhaseID(IntEnum):
    UNKOWN = 0
    RECONNAISSANCE = 1
    WEAPONIZATION = 2
    DELIVERY = 3
    EXPLOITATION = 4
    INSTALLATION = 5
    COMMAND_AND_CONTROL = 6
    ACTIONS_ON_OBJECTIVES = 7
    OTHER = 99


class KillChain(BaseModel):
    phase: KillChainPhase
    phase_id: KillChainPhaseID | None = None


class FindingInformation(BaseModel):
    """
    FindingInformation model represents the information about a vulnerability finding.
    https://schema.ocsf.io/1.5.0/objects/finding_information
    """

    uid: str
    data_sources: list[str] | None = None
    title: str | None = None
    src_url: str | None = None
    kill_chain: list[KillChain] | None = None
    desc: str | None = None


class CVE(BaseModel):
    uid: str
    type: str


class VulnerabilityDetails(BaseModel):
    title: str | None = None
    references: list[str]
    cve: CVE


# https://schema.ocsf.io/1.5.0/classes/vulnerability_finding
class VulnerabilityOCSFModel(BaseModel):
    device: Device | None = None
    finding_info: FindingInformation
    vulnerabilities: VulnerabilityDetails


## Assets Object Models


# TODO: Delete this model after complete migration to OCSF
# Compatible only with the fake asset connector
class AssetObject(BaseModel):
    name: str
    type: Literal["host", "account"]


# Union type for AssetItem, which can be one of the OCSF models or AssetObject
AssetItem = Union[
    VulnerabilityOCSFModel,
    DeviceOCSFModel,
    UserOCSFModel,
    SoftwareOCSFModel,
    AssetObject,
]


class AssetList(BaseModel):
    """
    AssetList model for OCSF.
    This model is used to represent a list of assets collected by an asset connector.
    Attributes:
        version (int): The OCSF schema version. ( Sekoia version )
        items (list): A list of asset objects, which can be of various types including
                      VulnerabilityOCSFModel, DeviceOCSFModel, UserOCSFModel, SoftwareOCSFModel, or AssetObject.
    """

    version: int
    items: Sequence[AssetItem] = []
