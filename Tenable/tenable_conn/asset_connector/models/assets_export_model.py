"""
Pydantic models for the Tenable Export Assets v2 chunk response.

Endpoint: GET /assets/export/{export_uuid}/chunks/{chunk_id}
Docs: https://developer.tenable.com/reference/exports-assets-download-chunk
"""

from typing import List, Optional

from pydantic import BaseModel


class AssetSource(BaseModel):
    name: str
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class AssetTag(BaseModel):
    uuid: str
    key: str
    value: str
    added_by: Optional[str] = None
    added_at: Optional[str] = None


class ResourceTag(BaseModel):
    key: str
    value: str


class OpenPort(BaseModel):
    port: Optional[int] = None
    protocol: Optional[str] = None
    service_names: List[str] = []
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class AcrScore(BaseModel):
    score: Optional[float] = None


class AesScore(BaseModel):
    score: Optional[float] = None


class Ratings(BaseModel):
    acr: Optional[AcrScore] = None
    aes: Optional[AesScore] = None


class NetworkInterfaceV2(BaseModel):
    name: Optional[str] = None
    mac_addresses: List[str] = []
    ipv4s: List[str] = []
    ipv6s: List[str] = []
    fqdns: List[str] = []
    virtual: Optional[bool] = None
    aliased: Optional[bool] = None


class AssetNetwork(BaseModel):
    network_id: Optional[str] = None
    network_name: Optional[str] = None
    bios_uuid: Optional[str] = None
    ipv4s: List[str] = []
    ipv6s: List[str] = []
    fqdns: List[str] = []
    mac_addresses: List[str] = []
    netbios_names: List[str] = []
    hostnames: List[str] = []
    ssh_fingerprints: List[str] = []
    network_interfaces: List[NetworkInterfaceV2] = []
    open_ports: List[OpenPort] = []


class AssetTimestamps(BaseModel):
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deleted_at: Optional[str] = None
    terminated_at: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class AssetScan(BaseModel):
    first_scan_time: Optional[str] = None
    last_scan_time: Optional[str] = None
    last_authenticated_scan_date: Optional[str] = None
    last_licensed_scan_date: Optional[str] = None
    last_scan_id: Optional[str] = None
    last_schedule_id: Optional[str] = None
    last_authentication_attempt_date: Optional[str] = None
    last_authentication_success_date: Optional[str] = None
    last_authentication_scan_status: Optional[str] = None
    last_scan_target: Optional[str] = None


class AwsCloud(BaseModel):
    ec2_instance_ami_id: Optional[str] = None
    ec2_instance_id: Optional[str] = None
    owner_id: Optional[str] = None
    availability_zone: Optional[str] = None
    region: Optional[str] = None
    vpc_id: Optional[str] = None
    ec2_instance_group_name: Optional[str] = None
    ec2_instance_state_name: Optional[str] = None
    ec2_instance_type: Optional[str] = None
    subnet_id: Optional[str] = None
    ec2_product_code: Optional[str] = None
    ec2_name: Optional[str] = None


class AzureCloud(BaseModel):
    vm_id: Optional[str] = None
    resource_id: Optional[str] = None


class GcpCloud(BaseModel):
    project_id: Optional[str] = None
    zone: Optional[str] = None
    instance_id: Optional[str] = None


class AssetCloud(BaseModel):
    aws: Optional[AwsCloud] = None
    azure: Optional[AzureCloud] = None
    gcp: Optional[GcpCloud] = None


class ThirdPartyIds(BaseModel):
    mcafee_epo_guid: Optional[str] = None
    mcafee_epo_agent_guid: Optional[str] = None
    servicenow_sysid: Optional[str] = None
    bigfix_asset_id: Optional[str] = None
    qualys_asset_ids: List[str] = []
    qualys_host_ids: List[str] = []
    symantec_ep_hardware_keys: List[str] = []


class CustomAttribute(BaseModel):
    id: Optional[str] = None
    value: Optional[str] = None


class AssetExportV2(BaseModel):
    """
    Asset record from the Export assets v2 chunk.
    """

    id: str
    has_agent: Optional[bool] = None
    has_plugin_results: Optional[bool] = None
    agent_uuid: Optional[str] = None
    is_licensed: Optional[bool] = None
    terminated_by: Optional[str] = None
    deleted_by: Optional[str] = None
    types: List[str] = []
    agent_names: List[str] = []
    operating_systems: List[str] = []
    system_types: List[str] = []
    manufacturer_tpm_ids: List[str] = []
    installed_software: List[str] = []
    is_public: Optional[bool] = None
    network_device_serial_identifier: Optional[str] = None
    custom_attributes: List[CustomAttribute] = []
    sources: List[AssetSource] = []
    tags: List[AssetTag] = []
    scan: Optional[AssetScan] = None
    cloud: Optional[AssetCloud] = None
    third_party_ids: Optional[ThirdPartyIds] = None
    network: Optional[AssetNetwork] = None
    timestamps: Optional[AssetTimestamps] = None
    ratings: Optional[Ratings] = None
    tenable_agent_days_since_active: Optional[int] = None
    resource_tags: List[ResourceTag] = []
    serial_number: Optional[str] = None

    model_config = {"extra": "allow"}
