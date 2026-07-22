from pydantic import BaseModel, ConfigDict


class HolmNetwork(BaseModel):
    """Network block of a Holm Security device record."""

    model_config = ConfigDict(extra="allow")

    ip_address: str | None = None
    ip_address_v6: str | None = None
    mac_address: str | None = None


class HolmDevice(BaseModel):
    """A single agent-managed device returned by ``GET /v2/devices``.

    Only the fields consumed by the OCSF mapping are declared; the API may
    return additional attributes, which are tolerated via ``extra="allow"``.
    """

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
    network: HolmNetwork | None = None


class HolmDevicePage(BaseModel):
    """Paginated response envelope for the devices endpoint."""

    model_config = ConfigDict(extra="allow")

    count: int = 0
    next: str | None = None
    previous: str | None = None
    results: list[HolmDevice] = []
