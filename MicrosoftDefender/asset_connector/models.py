from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    rbacGroupId: Optional[str] = None
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
