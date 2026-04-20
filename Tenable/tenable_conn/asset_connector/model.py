from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class TagsObject(BaseModel):
    tag_uuid: str
    tag_key: str
    tag_value: str
    added_by: str
    added_at: str

class SourceInfo(BaseModel):
    name: str
    first_seen: str
    last_seen: str


class NetworkInterface(BaseModel):
    ipv4: List[str] = []
    ipv6: List[str] = []
    fqdn: List[str] = []
    mac_address: List[str] = []
    name: Optional[str] = None
    virtual: Optional[bool] = None
    aliased: Optional[bool] = None


class AssetInfo(BaseModel):
    id: str
    name: Optional[str] = None
    has_agent: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    terminated_at: Optional[str] = None
    deleted_at: Optional[str] = None
    aes_score_v3: Optional[str] = None
    acr_score_v3: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    last_scan_target: Optional[str] = None
    last_authentication_attempt_date: Optional[str] = None
    last_authentication_success_date: Optional[str] = None
    last_authenticated_scan_date: Optional[str] = None
    last_licensed_scan_date: Optional[str] = None
    last_scan_id: Optional[str] = None
    last_schedule_id: Optional[str] = None
    sources: List[SourceInfo] = []
    tags: List[TagsObject] = []
    acr_score: Optional[Any] = None
    acr_drivers: Optional[Any] = None
    exposure_score: Optional[Any] = None
    scan_frequency: Optional[Any] = None
    interfaces: List[NetworkInterface] = []
    network_id: List[str] = []
    ipv4: List[str] = []
    ipv6: List[str] = []
    fqdn: List[str] = []
    mac_address: List[str] = []
    netbios_name: List[str] = []
    operating_system: List[str] = []
    system_type: List[str] = []
    tenable_uuid: List[str] = []
    hostname: List[str] = []
    agent_name: List[str] = []
    bios_uuid: List[str] = []
    # AWS
    aws_ec2_instance_id: List[str] = []
    aws_ec2_instance_ami_id: List[str] = []
    aws_owner_id: List[str] = []
    aws_availability_zone: List[str] = []
    aws_region: List[str] = []
    aws_vpc_id: List[str] = []
    aws_ec2_instance_group_name: List[str] = []
    aws_ec2_instance_state_name: List[str] = []
    aws_ec2_instance_type: List[str] = []
    aws_subnet_id: List[str] = []
    aws_ec2_product_code: List[str] = []
    aws_ec2_name: List[str] = []
    # Azure
    azure_vm_id: List[str] = []
    azure_resource_id: List[str] = []
    azure_subscription_id: List[str] = []
    azure_resource_group: List[str] = []
    azure_location: List[str] = []
    azure_type: List[str] = []
    # GCP
    gcp_project_id: List[str] = []
    gcp_zone: List[str] = []
    gcp_instance_id: List[str] = []
    # Misc
    ssh_fingerprint: List[str] = []
    mcafee_epo_guid: List[str] = []
    mcafee_epo_agent_guid: List[str] = []
    qualys_asset_id: List[str] = []
    qualys_host_id: List[str] = []
    servicenow_sysid: List[str] = []
    installed_software: List[str] = []
    bigfix_asset_id: List[str] = []
    security_protection_level: Optional[Any] = None
    security_protections: List[Any] = []
    exposure_confidence_value: Optional[Any] = None

    model_config = {"extra": "allow"}


class VulnAsset(BaseModel):
    uuid: str
    agent_uuid: Optional[str] = None
    device_type: Optional[str] = None
    fqdn: Optional[str] = None
    hostname: Optional[str] = None


class CvssTemporalVector(BaseModel):
    exploitability: Optional[str] = None
    remediation_level: Optional[str] = None
    report_confidence: Optional[str] = None
    raw: Optional[str] = None


class CvssVector(BaseModel):
    access_complexity: Optional[str] = None
    access_vector: Optional[str] = None
    authentication: Optional[str] = None
    availability_impact: Optional[str] = None
    confidentiality_impact: Optional[str] = None
    integrity_impact: Optional[str] = None
    raw: Optional[str] = None


class Cvss3Vector(BaseModel):
    access_complexity: Optional[str] = None
    access_vector: Optional[str] = None
    availability_impact: Optional[str] = None
    confidentiality_impact: Optional[str] = None
    integrity_impact: Optional[str] = None
    raw: Optional[str] = None


class VprDrivers(BaseModel):
    age_of_vuln: Optional[Dict[str, Any]] = None
    exploit_code_maturity: Optional[str] = None
    cvss3_impact_score: Optional[float] = None
    threat_intensity_last28: Optional[str] = None
    threat_sources_last28: List[str] = []
    product_coverage: Optional[str] = None


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
    in_the_news_intensity_last30: Optional[str] = None
    in_the_news_recency: Optional[str] = None
    malware_observations_intensity_last30: Optional[str] = None
    malware_observations_recency: Optional[str] = None


class Xref(BaseModel):
    type: str
    id: str


class Plugin(BaseModel):
    id: int
    name: Optional[str] = None
    family: Optional[str] = None
    family_id: Optional[int] = None
    description: Optional[str] = None
    synopsis: Optional[str] = None
    solution: Optional[str] = None
    risk_factor: Optional[str] = None
    version: Optional[str] = None
    publication_date: Optional[str] = None
    modification_date: Optional[str] = None
    patch_publication_date: Optional[str] = None
    vuln_publication_date: Optional[str] = None
    bid: List[int] = []
    cve: List[str] = []
    cpe: List[str] = []
    xrefs: List[Xref] = []
    see_also: List[str] = []
    # CVSS
    cvss_base_score: Optional[float] = None
    cvss_temporal_score: Optional[float] = None
    cvss_vector: Optional[CvssVector] = None
    cvss_temporal_vector: Optional[CvssTemporalVector] = None
    cvss3_base_score: Optional[float] = None
    cvss3_temporal_score: Optional[float] = None
    cvss3_vector: Optional[Cvss3Vector] = None
    cvss3_temporal_vector: Optional[CvssTemporalVector] = None
    # Exploit
    exploit_available: Optional[bool] = None
    exploit_framework_canvas: Optional[bool] = None
    exploit_framework_core: Optional[bool] = None
    exploit_framework_d2_elliot: Optional[bool] = None
    exploit_framework_exploithub: Optional[bool] = None
    exploit_framework_metasploit: Optional[bool] = None
    exploitability_ease: Optional[str] = None
    exploited_by_malware: Optional[bool] = None
    exploited_by_nessus: Optional[bool] = None
    # Flags
    checks_for_default_account: Optional[bool] = None
    checks_for_malware: Optional[bool] = None
    has_patch: Optional[bool] = None
    has_workaround: Optional[bool] = None
    in_the_news: Optional[bool] = None
    unsupported_by_vendor: Optional[bool] = None
    # VPR
    vpr: Optional[Vpr] = None
    vpr_v2: Optional[VprV2] = None
    epss_score: Optional[float] = None
    type: Optional[str] = None

    model_config = {"extra": "allow"}


class Port(BaseModel):
    port: Optional[int] = None
    protocol: Optional[str] = None


class Scan(BaseModel):
    uuid: Optional[str] = None
    schedule_uuid: Optional[str] = None
    started_at: Optional[str] = None
    target: Optional[str] = None


class Vulnerability(BaseModel):
    finding_id: Optional[str] = None
    asset: VulnAsset
    plugin: Plugin
    port: Optional[Port] = None
    scan: Optional[Scan] = None
    output: Optional[str] = None
    severity: Optional[str] = None
    severity_id: Optional[int] = None
    severity_default_id: Optional[int] = None
    severity_modification_type: Optional[str] = None
    state: Optional[str] = None
    source: Optional[str] = None
    first_found: Optional[str] = None
    last_found: Optional[str] = None
    indexed: Optional[str] = None

    model_config = {"extra": "allow"}
