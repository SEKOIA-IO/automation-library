from typing import Any

from pydantic.v1 import BaseModel


class HarfanglabAdditionalInfo(BaseModel):
    additional_info1: str | None = None
    additional_info2: str | None = None
    additional_info3: str | None = None
    additional_info4: str | None = None

    class Config:
        extra = "allow"


class HarfanglabGroup(BaseModel):
    id: str | None = None
    name: str | None = None

    class Config:
        extra = "allow"


class HarfanglabSubnet(BaseModel):
    gateway_ipaddress: str | None = None
    gateway_macaddress: str | None = None
    gateway_oui: str | None = None
    id: str | None = None
    name: str | None = None

    class Config:
        extra = "allow"


class HarfanglabOriginStack(BaseModel):
    id: str | None = None
    is_current: bool | None = None
    is_supervisor: bool | None = None
    is_tenant: bool | None = None
    name: str | None = None

    class Config:
        extra = "allow"


class HarfanglabPolicy(BaseModel):
    agent_auto_forget: bool | None = None
    agent_auto_forget_max_days: int | None = None
    agent_auto_update: bool | None = None
    agent_count: int | None = None
    agent_ui_admin_message: str | None = None
    agent_ui_enabled: bool | None = None
    agent_ui_notification_level: int | None = None
    agent_ui_notification_scope: int | None = None
    antivirus_policy: str | None = None
    antivirus_policy_name: str | None = None
    antivirus_profile: str | None = None
    antivirus_profile_name: str | None = None
    audit_killswitch: bool | None = None
    binary_download_enabled: bool | None = None
    description: str | None = None
    driverblock_mode: int | None = None
    feature_callback_tampering: bool | None = None
    feature_dse_tampering_mode: int | None = None
    feature_event_stacktrace: bool | None = None
    feature_live_process_heuristics: bool | None = None
    feature_ppl_antimalware: bool | None = None
    feature_process_tampering: bool | None = None
    feature_windows_filesystem_events: bool | None = None
    fim_policy: str | None = None
    firewall_policy: str | None = None
    hibou_minimum_level: str | None = None
    hibou_mode: int | None = None
    hibou_skip_signed_ms: bool | None = None
    hibou_skip_signed_others: bool | None = None
    hlai_minimum_level: str | None = None
    hlai_mode: int | None = None
    hlai_pdf: bool | None = None
    hlai_scan_libraries: bool | None = None
    hlai_scripts_minimum_level: str | None = None
    hlai_scripts_mode: int | None = None
    hlai_skip_signed_ms: bool | None = None
    hlai_skip_signed_others: bool | None = None
    hlai_written_executable: bool | None = None
    id: str | None = None
    ioc_mode: int | None = None
    ioc_ruleset: str | None = None
    ioc_scan_libraries: bool | None = None
    ioc_scan_written_executable: bool | None = None
    isolation_exclusions_revision: int | None = None
    library_download_enabled: bool | None = None
    linux_exclusions: int | None = None
    linux_paths_other_watched_globs: list[str] | None = None
    linux_self_protection: bool | None = None
    linux_self_protection_feature_hosts: bool | None = None
    linux_startup_block: bool | None = None
    linux_use_isolation: bool | None = None
    local_endpoint_cache_size: int | None = None
    loglevel: str | None = None
    macos_exclusions: int | None = None
    macos_paths_muted_exact: list[str] | None = None
    macos_paths_muted_globs: list[str] | None = None
    macos_paths_muted_prefixes: list[str] | None = None
    macos_paths_other_watched_exact: list[str] | None = None
    macos_paths_other_watched_globs: list[str] | None = None
    macos_paths_other_watched_prefixes: list[str] | None = None
    macos_paths_read_watched_exact: list[str] | None = None
    macos_paths_read_watched_globs: list[str] | None = None
    macos_paths_read_watched_prefixes: list[str] | None = None
    macos_paths_write_watched_exact: list[str] | None = None
    macos_paths_write_watched_globs: list[str] | None = None
    macos_paths_write_watched_prefixes: list[str] | None = None
    name: str | None = None
    network_isolation_exclusions: int | None = None
    origin_stack: HarfanglabOriginStack | None = None
    ransomguard_heuristic_mode: int | None = None
    ransomguard_mode: int | None = None
    revision: int | None = None
    self_protection: bool | None = None
    self_protection_feature_hosts: bool | None = None
    self_protection_feature_safe_mode: bool | None = None
    self_protection_firewall: bool | None = None
    sidewatch_mode: int | None = None
    sigma_mode: int | None = None
    sigma_ruleset: str | None = None
    sleepjitter: int | None = None
    sleeptime: int | None = None
    synchronization_status: str | None = None
    telemetry_alerts_limit: bool | None = None
    telemetry_alerts_limit_value: int | None = None
    telemetry_authentication: bool | None = None
    telemetry_authentication_limit: bool | None = None
    telemetry_authentication_limit_value: int | None = None
    telemetry_authentication_state: str | None = None
    telemetry_dns_resolution: bool | None = None
    telemetry_dns_resolution_limit: bool | None = None
    telemetry_dns_resolution_limit_value: int | None = None
    telemetry_dns_resolution_state: str | None = None
    telemetry_dotnet_library_state: str | None = None
    telemetry_driverload: bool | None = None
    telemetry_driverload_limit: bool | None = None
    telemetry_driverload_limit_value: int | None = None
    telemetry_driverload_state: str | None = None
    telemetry_file_download_limit: bool | None = None
    telemetry_file_download_limit_value: int | None = None
    telemetry_file_download_state: str | None = None
    telemetry_file_limit: bool | None = None
    telemetry_file_limit_value: int | None = None
    telemetry_file_state: str | None = None
    telemetry_library_load_limit: bool | None = None
    telemetry_library_load_limit_value: int | None = None
    telemetry_library_load_state: str | None = None
    telemetry_log: bool | None = None
    telemetry_log_limit: bool | None = None
    telemetry_log_limit_value: int | None = None
    telemetry_log_state: str | None = None
    telemetry_named_pipe_limit: bool | None = None
    telemetry_named_pipe_limit_value: int | None = None
    telemetry_named_pipe_state: str | None = None
    telemetry_network: bool | None = None
    telemetry_network_limit: bool | None = None
    telemetry_network_limit_value: int | None = None
    telemetry_network_listen_limit: bool | None = None
    telemetry_network_listen_limit_value: int | None = None
    telemetry_network_listen_state: str | None = None
    telemetry_network_state: str | None = None
    telemetry_on_alert_enabled: bool | None = None
    telemetry_on_alert_post_alert_max_duration_secs: int | None = None
    telemetry_on_alert_post_alert_max_event_count: int | None = None
    telemetry_on_alert_pre_alert_event_count: int | None = None
    telemetry_powershell: bool | None = None
    telemetry_powershell_limit: bool | None = None
    telemetry_powershell_limit_value: int | None = None
    telemetry_powershell_state: str | None = None
    telemetry_process: bool | None = None
    telemetry_process_access_limit: bool | None = None
    telemetry_process_access_limit_value: int | None = None
    telemetry_process_access_state: str | None = None
    telemetry_process_limit: bool | None = None
    telemetry_process_limit_value: int | None = None
    telemetry_process_state: str | None = None
    telemetry_process_tamper_limit: bool | None = None
    telemetry_process_tamper_limit_value: int | None = None
    telemetry_process_tamper_state: str | None = None
    telemetry_raw_device_access_limit: bool | None = None
    telemetry_raw_device_access_limit_value: int | None = None
    telemetry_raw_device_access_state: str | None = None
    telemetry_raw_socket_creation_limit: bool | None = None
    telemetry_raw_socket_creation_limit_value: int | None = None
    telemetry_raw_socket_creation_state: str | None = None
    telemetry_registry_limit: bool | None = None
    telemetry_registry_limit_value: int | None = None
    telemetry_registry_state: str | None = None
    telemetry_remotethread: bool | None = None
    telemetry_remotethread_limit: bool | None = None
    telemetry_remotethread_limit_value: int | None = None
    telemetry_remotethread_state: str | None = None
    telemetry_url_request_limit: bool | None = None
    telemetry_url_request_limit_value: int | None = None
    telemetry_url_request_state: str | None = None
    telemetry_usb_activity_limit: bool | None = None
    telemetry_usb_activity_limit_value: int | None = None
    telemetry_usb_activity_state: str | None = None
    telemetry_user_group_limit: bool | None = None
    telemetry_user_group_limit_value: int | None = None
    telemetry_user_group_state: str | None = None
    telemetry_wmi_event_limit: bool | None = None
    telemetry_wmi_event_limit_value: int | None = None
    telemetry_wmi_event_state: str | None = None
    tenant: str | None = None
    thread_download_enabled: bool | None = None
    use_driver: bool | None = None
    use_isolation: bool | None = None
    use_process_block: Any | None = None
    vulnerability_policy: str | None = None
    windows_exclusions: int | None = None
    windows_read_watched_paths: list[str] | None = None
    windows_registry_read_blacklist: list[str] | None = None
    windows_registry_read_whitelist: list[str] | None = None
    windows_self_protection: bool | None = None
    windows_self_protection_feature_firewall: bool | None = None
    windows_self_protection_feature_hosts: bool | None = None
    windows_self_protection_feature_safe_mode: bool | None = None
    windows_write_watched_paths: list[str] | None = None
    yara_mode: int | None = None
    yara_ruleset: str | None = None
    yara_scan_libraries_load: bool | None = None
    yara_scan_written_executable: bool | None = None
    yara_skip_signed_ms: bool | None = None
    yara_skip_signed_others: bool | None = None

    class Config:
        extra = "allow"


class HarfanglabAgent(BaseModel):
    id: str
    hostname: str
    firstseen: str

    additional_info: HarfanglabAdditionalInfo | None = None
    antivirus_last_update_date: str | None = None
    antivirus_name: str | None = None
    antivirus_rules_last_update_date: str | None = None
    antivirus_rules_version: str | None = None
    antivirus_version: str | None = None
    avg_av_cpu: float | None = None
    avg_av_memory: float | None = None
    avg_cpu: float | None = None
    avg_memory: float | None = None
    avg_system_cpu: float | None = None
    avg_system_memory: float | None = None
    bitness: str | None = None
    boot_loop_protection_boot_count: int | None = None
    boot_loop_protection_end_date: str | None = None
    cpu_count: int | None = None
    cpu_frequency: float | None = None
    description: str | None = None
    disk_count: int | None = None
    distroid: str | None = None
    dnsdomainname: str | None = None
    domain: str | None = None
    domainname: str | None = None
    driver_enabled: bool | None = None
    driver_policy: bool | None = None
    driver_version: str | None = None
    effective_driver_blocklists_revision: int | None = None
    effective_ioc_revision: int | None = None
    effective_sigma_revision: int | None = None
    effective_whitelist_revision: int | None = None
    effective_yara_revision: int | None = None
    encrypted_disk_count: int | None = None
    external_ipaddress: str | None = None
    group_count: int | None = None
    groups: list[HarfanglabGroup] | None = None
    has_valid_password: bool | None = None
    installdate: str | None = None
    ipaddress: str | None = None
    ipmask: str | None = None
    is_ppl_antimalware: bool | None = None
    isolation_policy: bool | None = None
    isolation_state: bool | None = None
    lastseen: str | None = None
    lastseen_error: str | None = None
    lastseen_warning: str | None = None
    machine_boottime: str | None = None
    machine_serial: str | None = None
    osbuild: int | None = None
    osid: str | None = None
    osmajor: int | None = None
    osminor: int | None = None
    osproducttype: str | None = None
    ostype: str | None = None
    osversion: str | None = None
    pinned_version: str | None = None
    policy: HarfanglabPolicy | None = None
    producttype: str | None = None
    quarantine_last_update: str | None = None
    refresh_properties_status: str | None = None
    refresh_quarantine_status: str | None = None
    rollback_version: str | None = None
    servicepack: str | None = None
    starttime: str | None = None
    status: str | None = None
    subnet: HarfanglabSubnet | None = None
    task_statuses: dict[str, Any] | None = None
    telemetry: dict[str, Any] | None = None
    telemetry_last_update: str | None = None
    tenant: str | None = None
    total_memory: int | None = None
    uninstall_status: int | None = None
    update_status: int | None = None
    version: str | None = None
    windows_groups_last_update: str | None = None
    windows_users_last_update: str | None = None

    class Config:
        extra = "allow"


class HarfanglabAgentPage(BaseModel):
    count: int = 0
    next: str | None = None
    previous: str | None = None
    results: list[HarfanglabAgent] = []

    class Config:
        extra = "allow"


class HarfanglabApplication(BaseModel):
    id: str
    name: str
    active: bool | None = None
    installation_date: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    first_version: str | None = None
    last_version: str | None = None
    installation_count: int | None = None
    publisher: str | None = None
    ostype: str | None = None
    cpe_prefix: str | None = None
    app_type: str | None = None
    description: str | None = None

    class Config:
        extra = "allow"


class HarfanglabApplicationPage(BaseModel):
    count: int = 0
    next: str | None = None
    previous: str | None = None
    results: list[HarfanglabApplication] = []

    class Config:
        extra = "allow"
