from pydantic import BaseModel, ConfigDict


class HolmNetwork(BaseModel):
    """Network block of a Holm Security device record."""

    model_config = ConfigDict(extra="allow")

    ip_address: str | None = None
    ip_address_v6: str | None = None
    mac_address: str | None = None


class HolmTag(BaseModel):
    """A tag attached to a Holm Security device."""

    model_config = ConfigDict(extra="allow")

    uuid: str
    name: str
    color: str | None = None
    is_dynamic: bool = False
    host_assets_cnt: int = 0
    da_assets_cnt: int = 0
    web_assets_cnt: int = 0
    cloud_assets_cnt: int = 0
    recipient_assets_cnt: int = 0


class HolmSeverityBreakdown(BaseModel):
    """Per-severity vulnerability counts for a device."""

    model_config = ConfigDict(extra="allow")

    info: int = 0
    low: int = 0
    medium: int = 0
    high: int = 0
    critical: int = 0


class HolmDevice(BaseModel):
    """A single agent-managed device returned by ``GET /v2/devices``."""

    model_config = ConfigDict(extra="allow")

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
    max_severity: str | None = None
    severity: HolmSeverityBreakdown | None = None
    current_version: str | None = None
    risk_score: int = 0


class HolmDevicePage(BaseModel):
    """Paginated response envelope for the devices endpoint."""

    model_config = ConfigDict(extra="allow")

    count: int = 0
    next: str | None = None
    previous: str | None = None
    results: list[HolmDevice] = []
