from typing import Any, cast

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.fields import FieldInfo


class HolmBaseModel(BaseModel):
    """Base model tolerating the explicit ``null`` values of the Holm Security API.

    Holm reports a field it has no value for as ``null`` instead of omitting it, and a
    pydantic default only applies to an absent key. Those nulls are dropped so the
    declared default applies: without this, a single ``"risk_score": null`` aborts the
    validation of the whole page and the connector collects nothing.

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


class HolmTag(HolmBaseModel):
    """A tag attached to a Holm Security device."""

    uuid: str
    name: str
    color: str | None = None
    is_dynamic: bool = False
    host_assets_cnt: int = 0
    da_assets_cnt: int = 0
    web_assets_cnt: int = 0
    cloud_assets_cnt: int = 0
    recipient_assets_cnt: int = 0


class HolmSeverityBreakdown(HolmBaseModel):
    """Per-severity vulnerability counts for a device."""

    info: int = 0
    low: int = 0
    medium: int = 0
    high: int = 0
    critical: int = 0


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
    internet_facing: bool = False
    internet_facing_user_override: bool = False
    debug_level: str | None = None
    error_interval: str | None = None
    update_interval: str | None = None
    user_account: str | None = None
    emails: list[str] = []
    tags: list[HolmTag] = []
    vuln_count: int = 0
    max_severity: int | str | None = None
    severity: HolmSeverityBreakdown | None = None
    current_version: str | None = None
    risk_score: int = 0


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
    hosts_personal_data: bool = False
    auth_status: str | None = None
    vulnerabilities_count: int = 0
    risk_score: int = 0
    severity: HolmSeverityBreakdown | None = None
    tags: list[HolmTag] = []
    open_ports: list[HolmOpenPort] = []


class HolmNetAssetPage(HolmBaseModel):
    """Paginated response envelope for the network assets endpoint."""

    count: int = 0
    next: str | None = None
    previous: str | None = None
    results: list[HolmNetAsset] = []
