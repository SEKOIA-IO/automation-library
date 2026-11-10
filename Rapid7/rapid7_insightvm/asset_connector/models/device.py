from pydantic import Field

from rapid7_insightvm.asset_connector.models.base import Rapid7BaseModel, Reference, StrId


class Rapid7Finding(Rapid7BaseModel):
    """An item of the ``new``, ``same`` or ``remediated`` lists of an asset.

    Only the mapped fields are declared: the others are kept untyped by ``extra="allow"``,
    so a type drift on an unmapped field never drops the finding.
    """

    vulnerability_id: Reference
    status: str | None = None
    key: str | None = None
    port: int | None = None
    protocol: str | None = None
    proof: str | None = None
    first_found: str | None = None
    last_found: str | None = None
    reintroduced: str | None = None
    remediation_date: str | None = None


class Rapid7Asset(Rapid7BaseModel):
    """An asset returned by ``POST /assets``.

    Only the mapped fields are declared: the others are kept untyped by ``extra="allow"``,
    so a type drift on an unmapped field never drops the asset.
    """

    id: StrId
    host_name: str | None = None
    ip: str | None = None
    type: str | None = None
    last_assessed_for_vulnerabilities: str | None = None
    new: list[Rapid7Finding] = Field(default_factory=list)
    same: list[Rapid7Finding] = Field(default_factory=list)
    remediated: list[Rapid7Finding] = Field(default_factory=list)
