from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


def resolve_hostname(computer_dns_name: Optional[str]) -> tuple[str, Optional[str]]:
    """Split a Defender computerDnsName into its short hostname and its domain."""
    if not computer_dns_name:
        return "", None
    short_name, _, domain = computer_dns_name.strip().partition(".")
    return short_name, domain or None


class DefenderMachine(BaseModel):
    """Model for a machine from the Defender for Endpoint API."""

    model_config = ConfigDict(extra="allow")

    id: str
    computerDnsName: Optional[str] = None
    firstSeen: Optional[str] = None
    lastSeen: Optional[str] = None
    osPlatform: Optional[str] = None
    onboardingstatus: Optional[str] = None
    osProcessor: Optional[str] = None
    version: Optional[str] = None
    osBuild: Optional[int] = None
    lastIpAddress: Optional[str] = None
    lastExternalIpAddress: Optional[str] = None
    healthStatus: Optional[str] = None
    rbacGroupName: Optional[str] = None
    rbacGroupId: Optional[int] = None
    riskScore: Optional[str] = None
    exposureLevel: Optional[str] = None
    aadDeviceId: Optional[str] = None
    machineTags: list[str] = []
    deviceValue: Optional[str] = None
    ipAddresses: list[dict[str, Any]] = []
    osArchitecture: Optional[str] = None


class DefenderMachineListResponse(BaseModel):
    """Paginated response from GET /api/machines."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    value: list[DefenderMachine] = []
    odata_next_link: Optional[str] = Field(None, alias="@odata.nextLink")


class DefenderMachineVulnerability(BaseModel):
    """Model for a machine-vulnerability relation from
    GET /api/vulnerabilities/machinesVulnerabilities."""

    model_config = ConfigDict(extra="allow")

    id: str
    cveId: Optional[str] = None
    machineId: Optional[str] = None
    fixingKbId: Optional[str] = None
    productName: Optional[str] = None
    productVendor: Optional[str] = None
    productVersion: Optional[str] = None
    severity: Optional[str] = None


class DefenderMachineVulnerabilityListResponse(BaseModel):
    """Paginated response from GET /api/vulnerabilities/machinesVulnerabilities."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    value: list[DefenderMachineVulnerability] = []
    odata_next_link: Optional[str] = Field(None, alias="@odata.nextLink")


class DefenderVulnerability(BaseModel):
    """Model for a vulnerability (CVE) from GET /api/vulnerabilities."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    cvssV3: Optional[float] = None
    cvssVector: Optional[str] = None
    exposedMachines: Optional[int] = None
    publishedOn: Optional[str] = None
    updatedOn: Optional[str] = None
    firstDetected: Optional[str] = None
    publicExploit: Optional[bool] = None
    exploitVerified: Optional[bool] = None
    exploitInKit: Optional[bool] = None
    exploitTypes: list[str] = []
    exploitUris: list[str] = []
    cveSupportability: Optional[str] = None
    tags: list[str] = []


class DefenderVulnerabilityListResponse(BaseModel):
    """Paginated response from GET /api/vulnerabilities."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    value: list[DefenderVulnerability] = []
    odata_next_link: Optional[str] = Field(None, alias="@odata.nextLink")
