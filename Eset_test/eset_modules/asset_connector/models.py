from typing import Optional

from pydantic.v1 import BaseModel


class EsetOsVersion(BaseModel):
    id: Optional[str] = None
    major: Optional[int] = None
    minor: Optional[int] = None
    name: Optional[str] = None
    patch: Optional[int] = None

    class Config:
        extra = "allow"


class EsetOperatingSystem(BaseModel):
    bitness: Optional[int] = None
    displayName: Optional[str] = None
    editionId: Optional[int] = None
    familyId: Optional[int] = None
    version: Optional[EsetOsVersion] = None

    class Config:
        extra = "allow"


class EsetNetworkAdapter(BaseModel):
    caption: Optional[str] = None
    macAddress: Optional[str] = None
    malformedData: Optional[str] = None

    class Config:
        extra = "allow"


class EsetProcessor(BaseModel):
    architecture: Optional[str] = None
    caption: Optional[str] = None
    id: Optional[str] = None
    malformedData: Optional[str] = None
    manufacturer: Optional[str] = None

    class Config:
        extra = "allow"


class EsetHardDrive(BaseModel):
    capacityBytes: Optional[str] = None
    displayName: Optional[str] = None
    driveType: Optional[str] = None
    hardwareEncryptionSupported: Optional[bool] = None
    malformedData: Optional[str] = None
    manufacturerName: Optional[str] = None
    serialNumber: Optional[str] = None

    class Config:
        extra = "allow"


class EsetBios(BaseModel):
    manufacturer: Optional[str] = None
    serialNumber: Optional[str] = None
    uuid: Optional[str] = None

    class Config:
        extra = "allow"


class EsetHardwareProfile(BaseModel):
    bios: Optional[EsetBios] = None
    hardDrives: Optional[list[EsetHardDrive]] = None
    malformedData: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    networkAdapters: Optional[list[EsetNetworkAdapter]] = None
    processors: Optional[list[EsetProcessor]] = None
    resettableIdentifier: Optional[str] = None
    salt: Optional[str] = None

    class Config:
        extra = "allow"


class EsetDeployedComponent(BaseModel):
    displayName: Optional[str] = None
    version: Optional[EsetOsVersion] = None
    id: Optional[int] = None
    name: Optional[str] = None

    class Config:
        extra = "allow"


class EsetActivateDate(BaseModel):
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None

    class Config:
        extra = "allow"


class EsetActiveProduct(BaseModel):
    activateDate: Optional[EsetActivateDate] = None
    subscriptionUuid: Optional[str] = None
    unitPoolUuid: Optional[str] = None
    validityDate: Optional[EsetActivateDate] = None
    id: Optional[int] = None
    name: Optional[str] = None

    class Config:
        extra = "allow"


class EsetCloningConfiguration(BaseModel):
    cloneNamingPatterns: Optional[list[str]] = None
    securityGroupUuid: Optional[str] = None
    securityGroupDisplayName: Optional[str] = None

    class Config:
        extra = "allow"


class EsetDevice(BaseModel):
    uuid: str
    activeProducts: Optional[list[EsetActiveProduct]] = None
    displayName: Optional[str] = None
    description: Optional[str] = None
    deviceToken: Optional[str] = None
    deviceType: Optional[str] = None
    enrollmentStatus: Optional[str] = None
    functionalityProblemCount: Optional[int] = None
    functionalityStatus: Optional[str] = None
    hardwareProfiles: Optional[list[EsetHardwareProfile]] = None
    deployedComponents: Optional[list[EsetDeployedComponent]] = None
    isMaster: Optional[bool] = None
    isMobile: Optional[bool] = None
    isMuted: Optional[bool] = None
    lastSyncTime: Optional[str] = None
    managementDomain: Optional[str] = None
    cloningConfiguration: Optional[EsetCloningConfiguration] = None
    operatingSystem: Optional[EsetOperatingSystem] = None
    originalDisplayName: Optional[str] = None
    parentGroupUuid: Optional[str] = None
    primaryLocalIpAddress: Optional[str] = None
    publicIpAddress: Optional[str] = None
    tags: Optional[list[str]] = None
    etag: Optional[str] = None
    ownerUuid: Optional[str] = None

    class Config:
        extra = "allow"


class EsetDevicePage(BaseModel):
    devices: list[EsetDevice] = []
    nextPageToken: Optional[str] = None

    class Config:
        extra = "allow"


class EsetDeviceGroup(BaseModel):
    uuid: str
    displayName: Optional[str] = None
    isSecurityGroup: Optional[bool] = None
    linkedEntityType: Optional[str] = None
    parentGroupUuid: Optional[str] = None
    etag: Optional[str] = None

    class Config:
        extra = "allow"


class EsetDeviceGroupPage(BaseModel):
    deviceGroups: list[EsetDeviceGroup] = []
    nextPageToken: Optional[str] = None

    class Config:
        extra = "allow"


# --- Vulnerability management models (/v1/device-vulnerabilities) ---


class EsetVulnApplicationVersion(BaseModel):
    id: Optional[str] = None
    major: Optional[int] = None
    minor: Optional[int] = None
    name: Optional[str] = None
    patch: Optional[int] = None

    class Config:
        extra = "allow"


class EsetVulnApplication(BaseModel):
    developerDisplayName: Optional[str] = None
    displayName: Optional[str] = None
    version: Optional[EsetVulnApplicationVersion] = None
    uuid: Optional[str] = None

    class Config:
        extra = "allow"


class EsetVulnPackage(BaseModel):
    displayName: Optional[str] = None
    name: Optional[str] = None
    packageManagerType: Optional[str] = None
    reference: Optional[str] = None
    versionName: Optional[str] = None

    class Config:
        extra = "allow"


class EsetApplicationVulnerability(BaseModel):
    application: Optional[EsetVulnApplication] = None
    cveNumber: Optional[str] = None
    firstDetectTime: Optional[str] = None
    lastDetectTime: Optional[str] = None
    patchAvailable: Optional[bool] = None
    riskScore: Optional[int] = None
    severity: Optional[str] = None
    vulnerabilityId: Optional[int] = None

    class Config:
        extra = "allow"


class EsetOsVulnerability(BaseModel):
    osFamilyId: Optional[int] = None
    cveNumber: Optional[str] = None
    firstDetectTime: Optional[str] = None
    lastDetectTime: Optional[str] = None
    patchAvailable: Optional[bool] = None
    riskScore: Optional[int] = None
    severity: Optional[str] = None
    vulnerabilityId: Optional[int] = None

    class Config:
        extra = "allow"


class EsetPackageVulnerability(BaseModel):
    package: Optional[EsetVulnPackage] = None
    cveNumber: Optional[str] = None
    firstDetectTime: Optional[str] = None
    lastDetectTime: Optional[str] = None
    patchAvailable: Optional[bool] = None
    riskScore: Optional[int] = None
    severity: Optional[str] = None
    vulnerabilityId: Optional[int] = None

    class Config:
        extra = "allow"


class EsetDeviceVulnerability(BaseModel):
    availablePatchUuids: Optional[list[str]] = None
    deviceUuid: Optional[str] = None
    deviceGroupUuid: Optional[str] = None
    applicationVulnerability: Optional[EsetApplicationVulnerability] = None
    osVulnerability: Optional[EsetOsVulnerability] = None
    packageVulnerability: Optional[EsetPackageVulnerability] = None

    class Config:
        extra = "allow"


class EsetVulnerabilityPage(BaseModel):
    vulnerabilities: list[EsetDeviceVulnerability] = []
    nextPageToken: Optional[str] = None

    class Config:
        extra = "allow"
