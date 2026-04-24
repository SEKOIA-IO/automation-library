from typing import Any

from pydantic import BaseModel, Field


class PolicyEntry(BaseModel):
    """Represents a single CrowdStrike policy applied to a device."""

    model_config = {"extra": "ignore"}

    policy_type: str | None = None
    policy_id: str | None = None
    applied: bool | None = None
    settings_hash: str | None = None
    assigned_date: str | None = None
    applied_date: str | None = None
    rule_groups: list[Any] = Field(default_factory=list)
    uninstall_protection: str | None = None
    rule_set_id: str | None = None


class DeviceMeta(BaseModel):
    """Represents CrowdStrike internal metadata attached to a device."""

    model_config = {"extra": "ignore"}

    version: str | None = None
    version_string: str | None = None


class CrowdStrikeDevice(BaseModel):
    """
    Represents a device as returned by the CrowdStrike Falcon API.

    All fields are optional to accommodate partial API responses.
    Field names match the CrowdStrike API field names exactly.
    """

    model_config = {"extra": "ignore"}

    # Identity
    device_id: str | None = None
    cid: str | None = None
    instance_id: str | None = None
    serial_number: str | None = None

    # Agent
    agent_load_flags: str | None = None
    agent_local_time: str | None = None
    agent_version: str | None = None

    # Hardware / BIOS
    bios_manufacturer: str | None = None
    bios_version: str | None = None
    build_number: str | None = None
    chassis_type: str | None = None
    chassis_type_desc: str | None = None
    cpu_signature: str | None = None
    cpu_vendor: str | None = None
    kernel_version: str | None = None
    pointer_size: str | None = None
    system_manufacturer: str | None = None
    system_product_name: str | None = None

    # Network
    connection_ip: str | None = None
    connection_mac_address: str | None = None
    default_gateway_ip: str | None = None
    external_ip: str | None = None
    local_ip: str | None = None
    mac_address: str | None = None

    # Host identity
    hostname: str | None = None
    machine_domain: str | None = None

    # OS
    major_version: str | None = None
    minor_version: str | None = None
    os_build: str | None = None
    os_product_name: str | None = None
    os_version: str | None = None
    platform_id: str | None = None
    platform_name: str | None = None

    # Status / Containment
    filesystem_containment_status: str | None = None
    provision_status: str | None = None
    reduced_functionality_mode: str | None = None
    rtr_state: str | None = None
    safe_mode: str | None = None
    status: str | None = None

    # Timestamps
    first_seen: str | None = None
    last_login_timestamp: str | None = None
    last_reboot: str | None = None
    last_seen: str | None = None
    modified_timestamp: str | None = None

    # Last login
    last_login_user: str | None = None
    last_login_user_sid: str | None = None

    # Product / device type
    product_type: str | None = None
    product_type_desc: str | None = None

    # Cloud / service provider
    service_provider: str | None = None
    service_provider_account_id: str | None = None
    zone_group: str | None = None

    # Sensor config
    config_id_base: str | None = None
    config_id_build: str | None = None
    config_id_platform: str | None = None
    service_pack_minor: str | None = None

    # Policies
    policies: list[PolicyEntry] = Field(default_factory=list)
    device_policies: dict[str, PolicyEntry] = Field(default_factory=dict)

    # Groups
    groups: list[str] = Field(default_factory=list)
    group_hash: str | None = None

    # Tags / labels
    tags: list[str] = Field(default_factory=list)
    pod_labels: list[Any] = Field(default_factory=list)
    pod_annotations: list[Any] = Field(default_factory=list)

    # Metadata
    meta: DeviceMeta | None = None
