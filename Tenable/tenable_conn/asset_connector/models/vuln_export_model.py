"""
Pydantic models for the Tenable Export Vulnerabilities endpoint.

Endpoint: GET /vulns/export/{export_uuid}/chunks/{chunk_id}
Docs: https://developer.tenable.com/reference/exports-vulns-download-chunk
"""

from typing import Any, Dict, List, Optional, Union
from enum import StrEnum

from pydantic import BaseModel


class CvssTemporalVector(BaseModel):
    exploitability: Optional[str] = None
    remediation_level: Optional[str] = None
    report_confidence: Optional[str] = None
    raw: Optional[str] = None


class CvssVector(BaseModel):
    access_vector: Optional[str] = None
    access_complexity: Optional[str] = None
    authentication: Optional[str] = None
    confidentiality_impact: Optional[str] = None
    integrity_impact: Optional[str] = None
    availability_impact: Optional[str] = None
    raw: Optional[str] = None


class Cvss3TemporalVector(BaseModel):
    exploitability: Optional[str] = None
    remediation_level: Optional[str] = None
    report_confidence: Optional[str] = None
    raw: Optional[str] = None


class Cvss3Vector(BaseModel):
    access_vector: Optional[str] = None
    access_complexity: Optional[str] = None
    authentication: Optional[str] = None
    confidentiality_impact: Optional[str] = None
    integrity_impact: Optional[str] = None
    availability_impact: Optional[str] = None
    raw: Optional[str] = None


class AttackVector(StrEnum):
    NETWORK = "Network"
    ADJACENT = "Adjacent"
    LOCAL = "Local"
    PHYSICAL = "Physical"


class AttackComplexity(StrEnum):
    LOW = "Low"
    HIGH = "High"


class AttackRequirements(StrEnum):
    NONE = "None"
    PRESENT = "Present"


class PrivilegesRequired(StrEnum):
    NONE = "None"
    LOW = "Low"
    HIGH = "High"


class UserInteraction(StrEnum):
    NONE = "None"
    PASSIVE = "Passive"
    ACTIVE = "Active"


class ImpactLevel(StrEnum):
    HIGH = "High"
    LOW = "Low"
    NONE = "None"


class ExploitMaturity(StrEnum):
    NOT_DEFINED = "Not Defined"
    ATTACKED = "Attacked"
    PROOF_OF_CONCEPT = "Proof-of-Concept"
    UNREPORTED = "Unreported"


class Cvss4Vector(BaseModel):
    attack_vector: Optional[AttackVector] = None
    attack_complexity: Optional[AttackComplexity] = None
    attack_requirements: Optional[AttackRequirements] = None
    privileges_required: Optional[PrivilegesRequired] = None
    user_interaction: Optional[UserInteraction] = None
    vulnerable_system_confidentiality: Optional[ImpactLevel] = None
    vulnerable_system_integrity: Optional[ImpactLevel] = None
    vulnerable_system_availability: Optional[ImpactLevel] = None
    subsequent_system_confidentiality: Optional[ImpactLevel] = None
    subsequent_system_integrity: Optional[ImpactLevel] = None
    subsequent_system_availability: Optional[ImpactLevel] = None
    raw: Optional[str] = None


class Cvss4ThreatVector(BaseModel):
    threat_score: Optional[float] = None
    exploit_maturity: Optional[ExploitMaturity] = None
    raw: Optional[str] = None


class VprAgeOfVuln(BaseModel):
    lower_bound: Optional[int] = None
    upper_bound: Optional[int] = None


class VprThreatRecency(BaseModel):
    lower_bound: Optional[int] = None
    upper_bound: Optional[int] = None


class VprDrivers(BaseModel):
    age_of_vuln: Optional[VprAgeOfVuln] = None
    exploit_code_maturity: Optional[str] = None
    cvss_impact_score_predicted: Optional[bool] = None
    cvss3_impact_score: Optional[float] = None
    threat_intensity_last28: Optional[str] = None
    threat_sources_last28: List[str] = []
    product_coverage: Optional[str] = None
    threat_recency: Optional[VprThreatRecency] = None


class Vpr(BaseModel):
    score: Optional[float] = None
    drivers: Optional[VprDrivers] = None
    updated: Optional[str] = None


class VprV2(BaseModel):
    score: Optional[float] = None
    vpr_percentile: Optional[float] = None
    vpr_severity: Optional[str] = None
    exploit_probability: Optional[float] = None
    cve_id: Optional[str] = None
    exploit_code_maturity: Optional[str] = None
    on_cisa_kev: Optional[bool] = None
    exploit_chain: Optional[List[str]] = None
    in_the_news_intensity_last30: Optional[str] = None
    in_the_news_recency: Optional[str] = None
    in_the_news_sources_last30: Optional[List[str]] = None
    malware_observations_intensity_last30: Optional[str] = None
    malware_observations_recency: Optional[str] = None
    targeted_industries: Optional[List[str]] = None
    targeted_regions: Optional[List[str]] = None
    threat_summary: Optional[Dict[str, Any]] = None
    remediation: Optional[Dict[str, Any]] = None


class Xref(BaseModel):
    type: str
    id: str


class Plugin(BaseModel):
    id: int
    name: Optional[str] = None
    bid: List[int] = []
    canvas_package: Optional[str] = None
    checks_for_default_account: Optional[bool] = None
    checks_for_malware: Optional[bool] = None
    cpe: List[str] = []
    cvss_base_score: Optional[float] = None
    cvss_temporal_score: Optional[float] = None
    cvss_vector: Optional[CvssVector] = None
    cvss_temporal_vector: Optional[CvssTemporalVector] = None
    cvss3_base_score: Optional[float] = None
    cvss3_temporal_score: Optional[float] = None
    cvss3_vector: Optional[Cvss3Vector] = None
    cvss3_temporal_vector: Optional[Cvss3TemporalVector] = None
    cvss4_base_score: Optional[float] = None
    cvss4_vector: Optional[Cvss4Vector] = None
    cvss4_threat_vector: Optional[Cvss4ThreatVector] = None
    d2_elliot_name: Optional[str] = None
    description: Optional[str] = None
    exploit_available: Optional[bool] = None
    exploit_framework_canvas: Optional[bool] = None
    exploit_framework_core: Optional[bool] = None
    exploit_framework_d2_elliot: Optional[bool] = None
    exploit_framework_exploithub: Optional[bool] = None
    exploit_framework_metasploit: Optional[bool] = None
    exploitability_ease: Optional[str] = None
    exploited_by_malware: Optional[bool] = None
    exploited_by_nessus: Optional[bool] = None
    exploithub_sku: Optional[str] = None
    family: Optional[str] = None
    family_id: Optional[int] = None
    has_patch: Optional[bool] = None
    has_workaround: Optional[bool] = None
    in_the_news: Optional[bool] = None
    metasploit_name: Optional[str] = None
    ms_bulletin: Optional[List[str]] = None
    patch_publication_date: Optional[str] = None
    modification_date: Optional[str] = None
    publication_date: Optional[str] = None
    vuln_publication_date: Optional[str] = None
    risk_factor: Optional[str] = None
    see_also: List[str] = []
    solution: Optional[str] = None
    stig_severity: Optional[str] = None
    synopsis: Optional[str] = None
    type: Optional[str] = None
    unsupported_by_vendor: Optional[bool] = None
    usn: Optional[str] = None
    vendor_severity: Optional[str] = None
    vendor_unpatched: Optional[bool] = None
    version: Optional[str] = None
    workaround: Optional[str] = None
    workaround_published: Optional[str] = None
    workaround_type: Optional[str] = None
    xrefs: List[Xref] = []
    cve: List[str] = []
    vpr: Optional[Vpr] = None
    vpr_v2: Optional[VprV2] = None
    epss_score: Optional[float] = None

    model_config = {"extra": "allow"}


class VulnAsset(BaseModel):
    uuid: str
    agent_uuid: Optional[str] = None
    bios_uuid: Optional[str] = None
    device_type: Optional[str] = None
    fqdn: Optional[str] = None
    hostname: Optional[str] = None
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    last_authenticated_results: Optional[str] = None
    last_unauthenticated_results: Optional[str] = None
    mac_address: Optional[str] = None
    netbios_name: Optional[str] = None
    netbios_workgroup: Optional[str] = None
    operating_system: Optional[List[str]] = None
    serial_number: Optional[str] = None
    network_id: Optional[str] = None
    tracked: Optional[bool] = None


class Port(BaseModel):
    port: Optional[int] = None
    protocol: Optional[str] = None
    service: Optional[str] = None


class Scan(BaseModel):
    uuid: Optional[str] = None
    schedule_uuid: Optional[str] = None
    started_at: Optional[str] = None
    last_scan_target: Optional[str] = None


class SoftwareVulnFix(BaseModel):
    fix_type: Optional[str] = None
    value: Optional[str] = None


class SoftwareVulnItem(BaseModel):
    fix_available: Optional[bool] = None
    identifier: Optional[str] = None
    path: Optional[str] = None
    product: Optional[str] = None
    product_type: Optional[str] = None
    version: Optional[str] = None
    vendor: Optional[str] = None
    categories: List[str] = []
    vulnerabilities: List[str] = []
    fixes: List[SoftwareVulnFix] = []
    potential: Optional[bool] = None
    potential_reasons: Optional[List[str]] = None


class Vulnerability(BaseModel):
    asset: VulnAsset
    plugin: Plugin
    output: Optional[str] = None
    port: Optional[Port] = None
    recast_reason: Optional[str] = None
    recast_rule_uuid: Optional[str] = None
    scan: Optional[Scan] = None
    severity: Optional[str] = None
    severity_id: Optional[int] = None
    severity_default_id: Optional[int] = None
    severity_modification_type: Optional[str] = None
    first_found: Optional[str] = None
    last_fixed: Optional[str] = None
    last_found: Optional[str] = None
    indexed: Optional[str] = None
    state: Optional[str] = None
    source: Optional[str] = None
    finding_id: Optional[str] = None
    resurfaced_date: Optional[str] = None
    time_taken_to_fix: Optional[Union[str, int]] = None
    software_vulns: Optional[List[SoftwareVulnItem]] = None

    model_config = {"extra": "allow"}
