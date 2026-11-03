from typing import Any, cast

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.fields import FieldInfo


class HolmBaseModel(BaseModel):
    """Base model tolerating the explicit ``null`` values of the Holm Security API.

    Holm reports a field it has no value for as ``null`` instead of omitting it, and a
    pydantic default only applies to an absent key: a single ``"risk_score": null`` or
    ``"open_ports": null`` on one network asset aborted the validation of the whole page
    and the connector collected nothing.

    Those nulls are dropped so the declared default applies. Every optional scalar
    defaults to ``None`` so a null is never turned into a fabricated value: only a
    collection falls back to an empty one, where ``null`` and ``[]`` mean the same thing.

    Nulls on required fields are kept so a genuinely malformed record still fails.
    """

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _null_to_default(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # `cls.model_fields` is typed as an instance property, hence the cast.
        fields = cast(dict[str, FieldInfo], cls.model_fields)

        return {
            key: value
            for key, value in data.items()
            if value is not None or key not in fields or fields[key].is_required()
        }


class HolmNetwork(HolmBaseModel):
    """Network block of a Holm Security device record."""

    ip_address: str | None = None
    ip_address_v6: str | None = None
    mac_address: str | None = None


class HolmDeviceEmail(HolmBaseModel):
    """A notification recipient attached to a Holm Security device."""

    email: str | None = None
    username: str | None = None


class HolmTag(HolmBaseModel):
    """A tag attached to a Holm Security device or network asset.

    Devices carry a full tag object, network assets a minimal one holding only a name
    and a uuid, so every field is optional.
    """

    uuid: str | None = None
    name: str | None = None
    color: str | None = None
    is_dynamic: bool | None = None
    host_assets_cnt: int | None = None
    da_assets_cnt: int | None = None
    web_assets_cnt: int | None = None
    cloud_assets_cnt: int | None = None
    recipient_assets_cnt: int | None = None


class HolmSeverityBreakdown(HolmBaseModel):
    """Per-severity vulnerability counts for a device."""

    info: int | None = None
    low: int | None = None
    medium: int | None = None
    high: int | None = None
    critical: int | None = None


class HolmDevice(HolmBaseModel):
    """A single agent-managed device returned by ``GET /v2/devices``."""

    uid: str
    device_name: str | None = None
    hostname: str | None = None
    state: str | None = None
    last_sync: str | None = None
    created: str | None = None
    os_is_server: bool | None = None
    os_family: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    os_build: str | None = None
    network: HolmNetwork | None = None
    internet_facing: bool | None = None
    internet_facing_user_override: bool | None = None
    debug_level: str | None = None
    error_interval: str | None = None
    update_interval: str | None = None
    user_account: str | None = None
    emails: list[HolmDeviceEmail] = []
    tags: list[HolmTag] = []
    vuln_count: int | None = None
    max_severity: int | str | None = None
    severity: HolmSeverityBreakdown | None = None
    current_version: str | None = None
    risk_score: int | None = None


class HolmDevicePage(HolmBaseModel):
    """Paginated response envelope for the devices endpoint."""

    count: int = 0
    next: str | None = None
    previous: str | None = None
    results: list[HolmDevice] = []


class HolmOpenPort(HolmBaseModel):
    """An open port reported on a Holm Security network asset."""

    proto: str | None = None
    port: int | None = None


class HolmNetAsset(HolmBaseModel):
    """A single scanned network asset returned by ``GET /v2/net-assets``.

    Network assets are hosts and IP ranges discovered by a scan, without an agent.
    """

    uuid: str
    name: str | None = None
    hostname: str | None = None
    ip: str | None = None
    ip_range: str | None = None
    type: str | None = None
    operating_system: str | None = None
    details: str | None = None
    created: str | None = None
    last_detected: str | None = None
    business_impact: str | None = None
    hosts_personal_data: bool | None = None
    auth_status: str | None = None
    vulnerabilities_count: int | None = None
    risk_score: int | None = None
    severity: HolmSeverityBreakdown | None = None
    tags: list[HolmTag] = []
    open_ports: list[HolmOpenPort] = []


class HolmNetAssetPage(HolmBaseModel):
    """Paginated response envelope for the network assets endpoint."""

    count: int = 0
    next: str | None = None
    previous: str | None = None
    results: list[HolmNetAsset] = []
