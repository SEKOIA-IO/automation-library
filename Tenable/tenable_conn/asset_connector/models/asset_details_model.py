"""
Pydantic models for the Tenable Get Asset Details endpoint.

Endpoint: GET /assets/{asset_uuid}
Docs: https://developer.tenable.com/reference/assets-asset-info
"""

from typing import List, Optional
from enum import StrEnum
from pydantic import BaseModel


class SourceName(StrEnum):
    ACUNETIX_360 = "ACUNETIX_360"
    ACUNETIX_PREMIUM = "ACUNETIX_PREMIUM"
    AQUA_CSPM = "AQUA_CSPM"
    AQUA_CWPP = "AQUA_CWPP"
    ARMIS = "ARMIS"
    ASM = "ASM"
    AWS = "AWS"
    AWS_CONFIG = "AWS_CONFIG"
    AWS_EC2 = "AWS_EC2"
    AWS_INSPECTOR_CLASSIC = "AWS_INSPECTOR_CLASSIC"
    AWS_INSPECTOR_V2 = "AWS_INSPECTOR_V2"
    AWS_SECURITY_HUB = "AWS_SECURITY_HUB"
    AXONIUS = "AXONIUS"
    AZURE = "AZURE"
    AZURE_FA = "AZURE_FA"
    BIT_SIGHT = "BIT_SIGHT"
    BURPSUITE = "BURPSUITE"
    CARBON_BLACK = "CARBON_BLACK"
    CLONE_SYSTEMS = "CLONE_SYSTEMS"
    CLOUD = "CLOUD"
    CONSEC = "CONSEC"
    CORE_CLOUDRESOURCE = "CORE_CLOUDRESOURCE"
    CORTEX_XDR = "CORTEX_XDR"
    CROWDSTRIKE = "CROWDSTRIKE"
    CROWDSTRIKE_ENTERPRISE = "CROWDSTRIKE_ENTERPRISE"
    CYCOGNITO = "CYCOGNITO"
    DETECTIFY = "DETECTIFY"
    FORTIFY_DAST = "FORTIFY_DAST"
    GCP = "GCP"
    HACKER_ONE = "HACKER_ONE"
    INTUNE = "INTUNE"
    JAMF = "JAMF"
    MICROSOFT_AZURE = "MICROSOFT_AZURE"
    MICROSOFT_DEFENDER = "MICROSOFT_DEFENDER"
    MICROSOFT_DEFENDER_CLOUD = "MICROSOFT_DEFENDER_CLOUD"
    MICROSOFT_TVM = "MICROSOFT_TVM"
    NESSUS_AGENT = "NESSUS_AGENT"
    NESSUS_SCAN = "NESSUS_SCAN"
    NETSPARKER = "NETSPARKER"
    NODE_ZERO = "NODE_ZERO"
    ORCA = "ORCA"
    OUTPOST24 = "OUTPOST24"
    PRISMACLOUD = "PRISMACLOUD"
    PRISMACLOUD_CSPM = "PRISMACLOUD_CSPM"
    PURPLEMET = "PURPLEMET"
    PVS = "PVS"
    QUALYS = "QUALYS"
    QUALYS_WAS = "QUALYS_WAS"
    RAPID7_INSIGHT_APP_SEC = "RAPID7_INSIGHT_APP_SEC"
    RAPID7_INSIGHTVM = "RAPID7_INSIGHTVM"
    RAPID7_INSIGHTVM_CLOUD = "RAPID7_INSIGHTVM_CLOUD"
    RAPID_7 = "RAPID_7"
    RED_HAT_INSIGHTS = "RED_HAT_INSIGHTS"
    RISK_RECON = "RISK_RECON"
    SECURITY_CENTER = "SECURITY_CENTER"
    SECURITY_SCORE_CARD = "SECURITY_SCORE_CARD"
    SENTINEL_ONE = "SENTINEL_ONE"
    SERVICE_NOW = "SERVICE_NOW"
    SSM = "SSM"
    T_CS = "T.CS"
    T_IO = "T.IO"
    T_OT = "T.OT"
    TANIUM = "TANIUM"
    TIE_AD = "TIE AD"
    TIE_MEID = "TIE MEID"
    TIE = "TIE"
    UNCLASSIFIED = "UNCLASSIFIED"
    VERACODE_DAST = "VERACODE_DAST"
    WAS = "WAS"
    WHITEHAT = "WHITEHAT"
    WIZ_CONFIGURATION = "WIZ_CONFIGURATION"
    WIZ_ISSUES = "WIZ_ISSUES"
    WIZ_VULNERABILITY_MANAGEMENT = "WIZ_VULNERABILITY_MANAGEMENT"


class AssetDetailsSource(BaseModel):
    name: Optional[SourceName] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class AssetDetailsTag(BaseModel):
    tag_uuid: Optional[str] = None
    tag_key: Optional[str] = None
    tag_value: Optional[str] = None
    added_by: Optional[str] = None
    added_at: Optional[str] = None


class DriverNameValues(StrEnum):
    DEVICE_TYPE = "device_type"
    DEVICE_CAPABILITY = "device_capability"
    INTERNET_EXPOSURE = "internet_exposure"


class AcrDriversObject(BaseModel):
    driver_name: Optional[DriverNameValues] = None
    driver_value: List[str] = []


class ScanFrequencyObject(BaseModel):
    interval: Optional[int] = None
    frequency: Optional[int] = None
    licensed: Optional[bool] = None


class NetworkInterface(BaseModel):
    name: Optional[str] = None
    ipv4: List[str] = []
    ipv6: List[str] = []
    fqdn: List[str] = []
    mac_address: List[str] = []
    virtual: Optional[bool] = None
    aliased: Optional[bool] = None


class AssetDetails(BaseModel):
    name: Optional[str] = None
    id: str
    has_agent: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    terminated_at: Optional[str] = None
    deleted_at: Optional[str] = None
    aes_score_v3: Optional[float] = None
    acr_score_v3: Optional[float] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    last_scan_target: Optional[str] = None
    last_authentication_attempt_date: Optional[str] = None
    last_authentication_success_date: Optional[str] = None
    last_authenticated_scan_date: Optional[str] = None
    last_licensed_scan_date: Optional[str] = None
    last_scan_id: Optional[str] = None
    last_schedule_id: Optional[str] = None
    sources: List[AssetDetailsSource] = []
    tags: List[AssetDetailsTag] = []
    acr_score: Optional[float] = None
    acr_drivers: Optional[List[AcrDriversObject]] = None
    exposure_score: Optional[float] = None
    scan_frequency: Optional[List[ScanFrequencyObject]] = None
    network_id: Optional[List[str]] = []
    ipv4: Optional[List[str]] = []
    ipv6: Optional[List[str]] = []
    fqdn: Optional[List[str]] = []
    mac_address: Optional[List[str]] = []
    netbios_name: Optional[List[str]] = []
    operating_system: Optional[List[str]] = []
    system_type: List[str] = []
    tenable_uuid: Optional[List[str]] = []
    hostname: Optional[List[str]] = []
    agent_name: Optional[List[str]] = []
    bios_uuid: Optional[List[str]] = []
    interfaces: Optional[List[NetworkInterface]] = []
    aws_ec2_instance_id: Optional[List[str]] = []
    aws_ec2_instance_ami_id: Optional[List[str]] = []
    aws_owner_id: Optional[List[str]] = []
    aws_availability_zone: Optional[List[str]] = []
    aws_region: Optional[List[str]] = []
    aws_vpc_id: Optional[List[str]] = []
    aws_ec2_instance_group_name: Optional[List[str]] = []
    aws_ec2_instance_state_name: Optional[List[str]] = []
    aws_ec2_instance_type: Optional[List[str]] = []
    aws_subnet_id: Optional[List[str]] = []
    aws_ec2_product_code: Optional[List[str]] = []
    aws_ec2_name: Optional[List[str]] = []
    azure_vm_id: Optional[List[str]] = []
    azure_resource_id: Optional[List[str]] = []
    gcp_project_id: Optional[List[str]] = []
    gcp_zone: Optional[List[str]] = []
    gcp_instance_id: Optional[List[str]] = []
    ssh_fingerprint: Optional[List[str]] = []
    mcafee_epo_guid: Optional[List[str]] = []
    mcafee_epo_agent_guid: Optional[List[str]] = []
    qualys_asset_id: Optional[List[str]] = []
    qualys_host_id: Optional[List[str]] = []
    servicenow_sysid: Optional[List[str]] = []
    bigfix_asset_id: Optional[List[str]] = []
    installed_software: Optional[List[str]] = []
    security_protection_level: Optional[int] = None
    security_protections: Optional[List[str]] = []
    exposure_confidence_value: Optional[int] = None

    model_config = {"extra": "allow"}
