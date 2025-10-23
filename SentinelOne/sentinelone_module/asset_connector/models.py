"""SentinelOne data models for API responses."""

from typing import Any, Optional

from pydantic import BaseModel


class NetworkInterface(BaseModel):
    """SentinelOne Network Interface."""

    id: str
    name: Optional[str] = None
    physical: Optional[str] = None
    inet: list[str] | None = None
    inet6: list[str] | None = None
    gatewayMacAddress: Optional[str] = None
    gatewayIp: Optional[str] = None


class ActiveDirectory(BaseModel):
    """SentinelOne Active Directory information."""

    lastUserDistinguishedName: Optional[str] = None
    lastUserMemberOf: list[str] | None = None
    computerDistinguishedName: Optional[str] = None
    computerMemberOf: list[str] | None = None
    userPrincipalName: Optional[str] = None
    mail: Optional[str] = None


class Location(BaseModel):
    """SentinelOne Location."""

    id: str
    name: str
    scope: str


class Tag(BaseModel):
    """SentinelOne Tag."""

    id: str
    key: str
    value: str
    assignedAt: Optional[str] = None
    assignedBy: Optional[str] = None
    assignedById: Optional[str] = None


class SentinelOneAgent(BaseModel):
    """SentinelOne Agent/Device.

    Represents a complete agent/device entity from the SentinelOne API.
    """

    id: str
    createdAt: str
    updatedAt: str
    groupUpdatedAt: Optional[str] = None
    policyUpdatedAt: Optional[str] = None
    accountId: str
    accountName: Optional[str] = None
    siteId: str
    siteName: Optional[str] = None
    groupId: Optional[str] = None
    groupName: Optional[str] = None
    licenseKey: Optional[str] = None
    uuid: str
    agentVersion: Optional[str] = None
    networkInterfaces: list[NetworkInterface] | None = None
    domain: Optional[str] = None
    computerName: Optional[str] = None
    osName: Optional[str] = None
    osRevision: Optional[str] = None
    osArch: Optional[str] = None
    osUsername: Optional[str] = None
    osStartTime: Optional[str] = None
    osType: Optional[str] = None
    totalMemory: Optional[int] = None
    modelName: Optional[str] = None
    machineType: Optional[str] = None
    cpuId: Optional[str] = None
    cpuCount: Optional[int] = None
    coreCount: Optional[int] = None
    externalIp: Optional[str] = None
    groupIp: Optional[str] = None
    activeThreats: Optional[int] = None
    infected: Optional[bool] = None
    threatRebootRequired: Optional[bool] = None
    lastActiveDate: Optional[str] = None
    isActive: Optional[bool] = None
    isUpToDate: Optional[bool] = None
    networkStatus: Optional[str] = None
    registeredAt: Optional[str] = None
    isPendingUninstall: Optional[bool] = None
    isUninstalled: Optional[bool] = None
    isDecommissioned: Optional[bool] = None
    encryptedApplications: Optional[bool] = None
    lastLoggedInUserName: Optional[str] = None
    activeDirectory: Optional[ActiveDirectory] = None
    scanStatus: Optional[str] = None
    scanStartedAt: Optional[str] = None
    scanFinishedAt: Optional[str] = None
    scanAbortedAt: Optional[str] = None
    fullDiskScanLastUpdatedAt: Optional[str] = None
    mitigationMode: Optional[str] = None
    mitigationModeSuspicious: Optional[str] = None
    userActionsNeeded: list[str] | None = None
    missingPermissions: list[str] | None = None
    consoleMigrationStatus: Optional[str] = None
    appsVulnerabilityStatus: Optional[str] = None
    inRemoteShellSession: Optional[bool] = None
    allowRemoteShell: Optional[bool] = None
    locations: list[Location] | None = None
    locationType: Optional[str] = None
    externalId: Optional[str] = None
    serialNumber: Optional[str] = None
    machineSid: Optional[str] = None
    installerType: Optional[str] = None
    rangerVersion: Optional[str] = None
    rangerStatus: Optional[str] = None
    lastIpToMgmt: Optional[str] = None
    operationalState: Optional[str] = None
    operationalStateExpiration: Optional[str] = None
    remoteProfilingState: Optional[str] = None
    remoteProfilingStateExpiration: Optional[str] = None
    networkQuarantineEnabled: Optional[bool] = None
    firewallEnabled: Optional[bool] = None
    locationEnabled: Optional[bool] = None
    cloudProviders: Optional[dict[str, Any]] = None
    storageType: Optional[str] = None
    storageName: Optional[str] = None
    detectionState: Optional[str] = None
    firstFullModeTime: Optional[str] = None
    tags: Optional[dict[str, list[Tag]]] = None
    showAlertIcon: Optional[bool] = None
    lastSuccessfulScanDate: Optional[str] = None
    proxyStates: Optional[dict[str, bool]] = None
    containerizedWorkloadCounts: Optional[dict[str, int]] = None
    hasContainerizedWorkload: Optional[bool] = None
    isAdConnector: Optional[bool] = None
    isHyperAutomate: Optional[bool] = None
    activeProtection: list[str] | None = None
