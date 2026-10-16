"""Pydantic models of the Rapid7 InsightVM Security Console API v3.

Attribute names follow the API (camelCase) so a response validates without aliases.
Every field except the identifiers is optional: the console omits or nulls many of them
depending on the scan type and the version of the console.
"""

from typing import Annotated, Any, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator
from pydantic.fields import FieldInfo
from sekoia_automation.asset_connector.models.connector import DefaultAssetConnectorConfiguration


def _coerce_id(value: Any) -> Any:
    """Asset ids are integers and vulnerability ids are strings: both are kept as strings."""
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return value


StrId = Annotated[str, BeforeValidator(_coerce_id)]


class Rapid7BaseModel(BaseModel):
    """Base model tolerating the explicit ``null`` values of the InsightVM API.

    A pydantic default only applies to an absent key, so a single ``"hostNames": null``
    would fail the validation of a whole page. Nulls on optional fields are dropped so
    the declared default applies; nulls on required fields are kept so a genuinely
    malformed record still fails.
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


class Rapid7InsightVMConnectorConfiguration(DefaultAssetConnectorConfiguration):
    """Asset connector configuration extended with the API page size."""

    page_size: int = Field(default=200, ge=1, le=500)


# --- pagination ----------------------------------------------------------------


class Rapid7PageInfo(Rapid7BaseModel):
    """The ``page`` block of a paginated response (zero-based page numbers)."""

    number: int | None = None
    size: int | None = None
    totalPages: int | None = None
    totalResources: int | None = None


# --- assets ----------------------------------------------------------------------


class Rapid7HostName(Rapid7BaseModel):
    name: str | None = None
    source: str | None = None


class Rapid7OSFingerprint(Rapid7BaseModel):
    """The ``osFingerprint`` block of an asset."""

    description: str | None = None
    family: str | None = None
    product: str | None = None
    systemName: str | None = None
    type: str | None = None
    vendor: str | None = None
    version: str | None = None
    architecture: str | None = None


class Rapid7AssetHistoryEvent(Rapid7BaseModel):
    """An entry of the asset ``history`` (scans, imports, exceptions...)."""

    date: str | None = None
    type: str | None = None


class Rapid7AssetVulnerabilityCounts(Rapid7BaseModel):
    critical: int | None = None
    severe: int | None = None
    moderate: int | None = None
    total: int | None = None


class Rapid7Asset(Rapid7BaseModel):
    """An asset returned by ``GET /api/3/assets`` or ``POST /api/3/assets/search``."""

    id: StrId
    hostName: str | None = None
    hostNames: list[Rapid7HostName] = []
    ip: str | None = None
    mac: str | None = None
    os: str | None = None
    osFingerprint: Rapid7OSFingerprint | None = None
    type: str | None = None
    assessedForVulnerabilities: bool | None = None
    history: list[Rapid7AssetHistoryEvent] = []
    vulnerabilities: Rapid7AssetVulnerabilityCounts | None = None


class Rapid7AssetPage(Rapid7BaseModel):
    resources: list[Rapid7Asset] = []
    page: Rapid7PageInfo | None = None


# --- findings ----------------------------------------------------------------------


class Rapid7FindingResult(Rapid7BaseModel):
    """A test result of a finding (one per port/instance)."""

    checkId: str | None = None
    port: int | None = None
    protocol: str | None = None
    proof: str | None = None
    since: str | None = None
    reintroduced: str | None = None
    status: str | None = None


class Rapid7Finding(Rapid7BaseModel):
    """A finding returned by ``GET /api/3/assets/{id}/vulnerabilities``."""

    id: StrId
    status: str | None = None
    since: str | None = None
    instances: int | None = None
    results: list[Rapid7FindingResult] = []


class Rapid7FindingPage(Rapid7BaseModel):
    resources: list[Rapid7Finding] = []
    page: Rapid7PageInfo | None = None


# --- vulnerability definitions ------------------------------------------------------


class Rapid7Description(Rapid7BaseModel):
    html: str | None = None
    text: str | None = None


class Rapid7CVSSScore(Rapid7BaseModel):
    score: float | None = None
    vector: str | None = None


class Rapid7CVSS(Rapid7BaseModel):
    v2: Rapid7CVSSScore | None = None
    v3: Rapid7CVSSScore | None = None


class Rapid7Vulnerability(Rapid7BaseModel):
    """A vulnerability definition returned by ``GET /api/3/vulnerabilities/{id}``."""

    id: StrId
    title: str | None = None
    description: Rapid7Description | None = None
    cves: list[str] = []
    cvss: Rapid7CVSS | None = None
    severity: str | None = None
    riskScore: float | None = None
    fixAvailable: bool | None = None
    categories: list[str] = []
    added: str | None = None


class VulnerabilitySummary(BaseModel):
    """The subset of a vulnerability definition kept in the per-run cache.

    The description is stored already stripped of its HTML and truncated, so the cache
    holds only what the mapping needs.
    """

    id: str
    title: str | None = None
    desc: str | None = None
    cves: list[str] = []
    cvss_v2_score: float | None = None
    cvss_v3_score: float | None = None
    cvss_v3_version: str | None = None
    severity: str | None = None
    risk_score: float | None = None
    fix_available: bool | None = None
    categories: list[str] = []
    added: str | None = None
