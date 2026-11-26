from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.fields import FieldInfo


class WithSecureModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _null_to_default(cls, data: Any) -> Any:
        """
        Drop the explicit nulls of optional fields so their default applies:
        a pydantic default only replaces an absent key, and `"assetGroups": null` fails a list field.
        """
        if not isinstance(data, dict):
            return data

        # `cls.model_fields` is typed as an instance property, hence the cast.
        fields = cast(dict[str, FieldInfo], cls.model_fields)
        return {
            key: value
            for key, value in data.items()
            if value is not None or key not in fields or fields[key].is_required()
        }


class WithSecureCompany(WithSecureModel):
    id: str | None = None
    name: str | None = None


class WithSecureAssetGroup(WithSecureModel):
    id: str | None = None
    name: str | None = None


class WithSecureOS(WithSecureModel):
    name: str | None = None
    version: str | None = None


class WithSecureSubscription(WithSecureModel):
    productVariant: str | None = None


class WithSecureEncryptedDrive(WithSecureModel):
    drive: str | None = None
    protectionStatus: bool | None = None


class WithSecureDevice(WithSecureModel):
    """
    Device item of GET /devices/v1/devices.
    Computer-only fields are absent for `mobile` and `connector` devices.
    """

    id: str
    name: str | None = None
    type: str | None = None
    company: WithSecureCompany | None = None
    assetGroups: list[WithSecureAssetGroup] = []
    os: WithSecureOS | None = None
    subscription: WithSecureSubscription | None = None
    protectionStatusOverview: str | None = None
    registrationTimestamp: datetime | None = None
    statusUpdateTimestamp: datetime | None = None
    lastRestartTime: datetime | None = None
    computerModel: str | None = None
    serialNumber: str | None = None
    lastUser: str | None = None
    userPrincipalName: str | None = None
    email: str | None = None
    # comma-separated lists
    ipAddresses: str | None = None
    ipv6Addresses: str | None = None
    macAddresses: str | None = None
    dnsAddress: str | None = None
    firewallState: str | None = None
    discEncryptionEnabled: bool | None = None
    encryptedDrives: list[WithSecureEncryptedDrive] = []
    vmRiskScore: float | None = None
