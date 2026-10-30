from typing import Annotated, Any

from pydantic import BeforeValidator

from rapid7_insightvm.asset_connector.models.base import Rapid7BaseModel, Reference, StrId


def _as_list(value: Any) -> Any:
    if isinstance(value, dict):
        return [value]
    return value


class Rapid7Tag(Rapid7BaseModel):
    name: str | None = None
    type: str | None = None


class Rapid7UniqueIdentifier(Rapid7BaseModel):
    id: str | None = None
    source: str | None = None


class Rapid7CredentialAssessment(Rapid7BaseModel):
    port: int | None = None
    protocol: str | None = None
    status: str | None = None


class Rapid7Endpoint(Rapid7BaseModel):
    port: int | None = None
    protocol: str | None = None


class Rapid7Finding(Rapid7BaseModel):
    """An item of the ``new``, ``same`` or ``remediated`` lists of an asset."""

    vulnerability_id: Reference
    status: str | None = None
    check_id: Reference | None = None
    key: str | None = None
    nic: str | None = None
    port: int | None = None
    protocol: str | None = None
    endpoint: Rapid7Endpoint | None = None
    proof: str | None = None
    first_found: str | None = None
    last_found: str | None = None
    reintroduced: str | None = None
    remediation_date: str | None = None
    solution_id: Reference | None = None
    solution_type: str | None = None
    solution_summary: str | None = None
    solution_fix: str | None = None


class Rapid7Asset(Rapid7BaseModel):
    """An asset returned by ``POST /vm/v4/integration/assets``."""

    id: StrId
    host_name: str | None = None
    ip: str | None = None
    mac: str | None = None
    type: str | None = None
    os_architecture: str | None = None
    os_description: str | None = None
    os_family: str | None = None
    os_name: str | None = None
    os_system_name: str | None = None
    os_type: str | None = None
    os_vendor: str | None = None
    os_version: str | None = None
    assessed_for_policies: bool | None = None
    assessed_for_vulnerabilities: bool | None = None
    last_assessed_for_vulnerabilities: str | None = None
    last_scan_start: str | None = None
    last_scan_end: str | None = None
    credential_assessments: list[Rapid7CredentialAssessment] = []
    risk_score: float | None = None
    critical_vulnerabilities: int | None = None
    severe_vulnerabilities: int | None = None
    moderate_vulnerabilities: int | None = None
    total_vulnerabilities: int | None = None
    exploits: int | None = None
    malware_kits: int | None = None
    tags: list[Rapid7Tag] = []
    unique_identifiers: Annotated[list[Rapid7UniqueIdentifier], BeforeValidator(_as_list)] = []
    new: list[Rapid7Finding] = []
    same: list[Rapid7Finding] = []
    remediated: list[Rapid7Finding] = []
