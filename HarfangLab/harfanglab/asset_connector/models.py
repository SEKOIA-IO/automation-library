from typing import Any, Dict, List, Optional

from pydantic.v1 import BaseModel


class HarfanglabAdditionalInfo(BaseModel):
    additional_info1: Optional[str] = None
    additional_info2: Optional[str] = None
    additional_info3: Optional[str] = None
    additional_info4: Optional[str] = None

    class Config:
        extra = "allow"


class HarfanglabGroup(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

    class Config:
        extra = "allow"


class HarfanglabSubnet(BaseModel):
    gateway_ipaddress: Optional[str] = None
    gateway_macaddress: Optional[str] = None
    gateway_oui: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None

    class Config:
        extra = "allow"


class HarfanglabOriginStack(BaseModel):
    id: Optional[str] = None
    is_current: Optional[bool] = None
    is_supervisor: Optional[bool] = None
    is_tenant: Optional[bool] = None
    name: Optional[str] = None

    class Config:
        extra = "allow"


class HarfanglabPolicy(BaseModel):
    agent_auto_forget: Optional[bool] = None
    agent_auto_forget_max_days: Optional[int] = None
    agent_auto_update: Optional[bool] = None
    agent_count: Optional[int] = None
    agent_ui_admin_message: Optional[str] = None
    agent_ui_enabled: Optional[bool] = None
    agent_ui_notification_level: Optional[int] = None
    agent_ui_notification_scope: Optional[int] = None
    antivirus_policy: Optional[str] = None
    antivirus_policy_name: Optional[str] = None
    antivirus_profile: Optional[str] = None
    antivirus_profile_name: Optional[str] = None
    audit_killswitch: Optional[bool] = None
    binary_download_enabled: Optional[bool] = None
    description: Optional[str] = None
    driverblock_mode: Optional[int] = None
    feature_callback_tampering: Optional[bool] = None
    feature_dse_tampering_mode: Optional[int] = None
    feature_event_stacktrace: Optional[bool] = None
    feature_live_process_heuristics: Optional[bool] = None
    feature_ppl_antimalware: Optional[bool] = None
    feature_process_tampering: Optional[bool] = None
    feature_windows_filesystem_events: Optional[bool] = None
    fim_policy: Optional[str] = None
    firewall_policy: Optional[str] = None
    hibou_minimum_level: Optional[str] = None
    hibou_mode: Optional[int] = None
    hibou_skip_signed_ms: Optional[bool] = None
    hibou_skip_signed_others: Optional[bool] = None
    hlai_minimum_level: Optional[str] = None
    hlai_mode: Optional[int] = None
    hlai_pdf: Optional[bool] = None
    hlai_scan_libraries: Optional[bool] = None
    hlai_scripts_minimum_level: Optional[str] = None
    hlai_scripts_mode: Optional[int] = None
    hlai_skip_signed_ms: Optional[bool] = None
    hlai_skip_signed_others: Optional[bool] = None
    hlai_written_executable: Optional[bool] = None
    id: Optional[str] = None
    ioc_mode: Optional[int] = None
    ioc_ruleset: Optional[int] = None
    ioc_scan_libraries: Optional[bool] = None
    ioc_scan_written_executable: Optional[bool] = None
    isolation_exclusions_revision: Optional[int] = None
    library_download_enabled: Optional[bool] = None
    linux_exclusions: Optional[int] = None
    linux_paths_other_watched_globs: Optional[List[str]] = None
    linux_self_protection: Optional[bool] = None
    linux_self_protection_feature_hosts: Optional[bool] = None
    linux_startup_block: Optional[bool] = None
    linux_use_isolation: Optional[bool] = None
    local_endpoint_cache_size: Optional[int] = None
    loglevel: Optional[str] = None
    macos_exclusions: Optional[int] = None
    macos_paths_muted_exact: Optional[List[str]] = None
    macos_paths_muted_globs: Optional[List[str]] = None
    macos_paths_muted_prefixes: Optional[List[str]] = None
    macos_paths_other_watched_exact: Optional[List[str]] = None
    macos_paths_other_watched_globs: Optional[List[str]] = None
    macos_paths_other_watched_prefixes: Optional[List[str]] = None
    macos_paths_read_watched_exact: Optional[List[str]] = None
    macos_paths_read_watched_globs: Optional[List[str]] = None
    macos_paths_read_watched_prefixes: Optional[List[str]] = None
    macos_paths_write_watched_exact: Optional[List[str]] = None
    macos_paths_write_watched_globs: Optional[List[str]] = None
    macos_paths_write_watched_prefixes: Optional[List[str]] = None
    name: Optional[str] = None
    network_isolation_exclusions: Optional[int] = None
    origin_stack: Optional[HarfanglabOriginStack] = None
    ransomguard_heuristic_mode: Optional[int] = None
    ransomguard_mode: Optional[int] = None
    revision: Optional[int] = None
    self_protection: Optional[bool] = None
    self_protection_feature_hosts: Optional[bool] = None
    self_protection_feature_safe_mode: Optional[bool] = None
    self_protection_firewall: Optional[bool] = None
    sidewatch_mode: Optional[int] = None
    sigma_mode: Optional[int] = None
    sigma_ruleset: Optional[int] = None
    sleepjitter: Optional[int] = None
    sleeptime: Optional[int] = None
    synchronization_status: Optional[str] = None
    telemetry_alerts_limit: Optional[bool] = None
    telemetry_alerts_limit_value: Optional[int] = None
    telemetry_authentication: Optional[bool] = None
    telemetry_authentication_limit: Optional[bool] = None
    telemetry_authentication_limit_value: Optional[int] = None
    telemetry_authentication_state: Optional[str] = None
    telemetry_dns_resolution: Optional[bool] = None
    telemetry_dns_resolution_limit: Optional[bool] = None
    telemetry_dns_resolution_limit_value: Optional[int] = None
    telemetry_dns_resolution_state: Optional[str] = None
    telemetry_dotnet_library_state: Optional[str] = None
    telemetry_driverload: Optional[bool] = None
    telemetry_driverload_limit: Optional[bool] = None
    telemetry_driverload_limit_value: Optional[int] = None
    telemetry_driverload_state: Optional[str] = None
    telemetry_file_download_limit: Optional[bool] = None
    telemetry_file_download_limit_value: Optional[int] = None
    telemetry_file_download_state: Optional[str] = None
    telemetry_file_limit: Optional[bool] = None
    telemetry_file_limit_value: Optional[int] = None
    telemetry_file_state: Optional[str] = None
    telemetry_library_load_limit: Optional[bool] = None
    telemetry_library_load_limit_value: Optional[int] = None
    telemetry_library_load_state: Optional[str] = None
    telemetry_log: Optional[bool] = None
    telemetry_log_limit: Optional[bool] = None
    telemetry_log_limit_value: Optional[int] = None
    telemetry_log_state: Optional[str] = None
    telemetry_named_pipe_limit: Optional[bool] = None
    telemetry_named_pipe_limit_value: Optional[int] = None
    telemetry_named_pipe_state: Optional[str] = None
    telemetry_network: Optional[bool] = None
    telemetry_network_limit: Optional[bool] = None
    telemetry_network_limit_value: Optional[int] = None
    telemetry_network_listen_limit: Optional[bool] = None
    telemetry_network_listen_limit_value: Optional[int] = None
    telemetry_network_listen_state: Optional[str] = None
    telemetry_network_state: Optional[str] = None
    telemetry_on_alert_enabled: Optional[bool] = None
    telemetry_on_alert_post_alert_max_duration_secs: Optional[int] = None
    telemetry_on_alert_post_alert_max_event_count: Optional[int] = None
    telemetry_on_alert_pre_alert_event_count: Optional[int] = None
    telemetry_powershell: Optional[bool] = None
    telemetry_powershell_limit: Optional[bool] = None
    telemetry_powershell_limit_value: Optional[int] = None
    telemetry_powershell_state: Optional[str] = None
    telemetry_process: Optional[bool] = None
    telemetry_process_access_limit: Optional[bool] = None
    telemetry_process_access_limit_value: Optional[int] = None
    telemetry_process_access_state: Optional[str] = None
    telemetry_process_limit: Optional[bool] = None
    telemetry_process_limit_value: Optional[int] = None
    telemetry_process_state: Optional[str] = None
    telemetry_process_tamper_limit: Optional[bool] = None
    telemetry_process_tamper_limit_value: Optional[int] = None
    telemetry_process_tamper_state: Optional[str] = None
    telemetry_raw_device_access_limit: Optional[bool] = None
    telemetry_raw_device_access_limit_value: Optional[int] = None
    telemetry_raw_device_access_state: Optional[str] = None
    telemetry_raw_socket_creation_limit: Optional[bool] = None
    telemetry_raw_socket_creation_limit_value: Optional[int] = None
    telemetry_raw_socket_creation_state: Optional[str] = None
    telemetry_registry_limit: Optional[bool] = None
    telemetry_registry_limit_value: Optional[int] = None
    telemetry_registry_state: Optional[str] = None
    telemetry_remotethread: Optional[bool] = None
    telemetry_remotethread_limit: Optional[bool] = None
    telemetry_remotethread_limit_value: Optional[int] = None
    telemetry_remotethread_state: Optional[str] = None
    telemetry_url_request_limit: Optional[bool] = None
    telemetry_url_request_limit_value: Optional[int] = None
    telemetry_url_request_state: Optional[str] = None
    telemetry_usb_activity_limit: Optional[bool] = None
    telemetry_usb_activity_limit_value: Optional[int] = None
    telemetry_usb_activity_state: Optional[str] = None
    telemetry_user_group_limit: Optional[bool] = None
    telemetry_user_group_limit_value: Optional[int] = None
    telemetry_user_group_state: Optional[str] = None
    telemetry_wmi_event_limit: Optional[bool] = None
    telemetry_wmi_event_limit_value: Optional[int] = None
    telemetry_wmi_event_state: Optional[str] = None
    tenant: Optional[str] = None
    thread_download_enabled: Optional[bool] = None
    use_driver: Optional[bool] = None
    use_isolation: Optional[bool] = None
    use_process_block: Optional[Any] = None
    vulnerability_policy: Optional[str] = None
    windows_exclusions: Optional[int] = None
    windows_read_watched_paths: Optional[List[str]] = None
    windows_registry_read_blacklist: Optional[List[str]] = None
    windows_registry_read_whitelist: Optional[List[str]] = None
    windows_self_protection: Optional[bool] = None
    windows_self_protection_feature_firewall: Optional[bool] = None
    windows_self_protection_feature_hosts: Optional[bool] = None
    windows_self_protection_feature_safe_mode: Optional[bool] = None
    windows_write_watched_paths: Optional[List[str]] = None
    yara_mode: Optional[int] = None
    yara_ruleset: Optional[int] = None
    yara_scan_libraries_load: Optional[bool] = None
    yara_scan_written_executable: Optional[bool] = None
    yara_skip_signed_ms: Optional[bool] = None
    yara_skip_signed_others: Optional[bool] = None

    class Config:
        extra = "allow"


class HarfanglabAgent(BaseModel):
    id: str
    hostname: str
    firstseen: str

    additional_info: Optional[HarfanglabAdditionalInfo] = None
    antivirus_last_update_date: Optional[str] = None
    antivirus_name: Optional[str] = None
    antivirus_rules_last_update_date: Optional[str] = None
    antivirus_rules_version: Optional[str] = None
    antivirus_version: Optional[str] = None
    avg_av_cpu: Optional[float] = None
    avg_av_memory: Optional[float] = None
    avg_cpu: Optional[float] = None
    avg_memory: Optional[float] = None
    avg_system_cpu: Optional[float] = None
    avg_system_memory: Optional[float] = None
    bitness: Optional[str] = None
    boot_loop_protection_boot_count: Optional[int] = None
    boot_loop_protection_end_date: Optional[str] = None
    cpu_count: Optional[int] = None
    cpu_frequency: Optional[float] = None
    description: Optional[str] = None
    disk_count: Optional[int] = None
    distroid: Optional[str] = None
    dnsdomainname: Optional[str] = None
    domain: Optional[str] = None
    domainname: Optional[str] = None
    driver_enabled: Optional[bool] = None
    driver_policy: Optional[bool] = None
    driver_version: Optional[str] = None
    effective_driver_blocklists_revision: Optional[int] = None
    effective_ioc_revision: Optional[int] = None
    effective_sigma_revision: Optional[int] = None
    effective_whitelist_revision: Optional[int] = None
    effective_yara_revision: Optional[int] = None
    encrypted_disk_count: Optional[int] = None
    external_ipaddress: Optional[str] = None
    group_count: Optional[int] = None
    groups: Optional[List[HarfanglabGroup]] = None
    has_valid_password: Optional[bool] = None
    installdate: Optional[str] = None
    ipaddress: Optional[str] = None
    ipmask: Optional[str] = None
    is_ppl_antimalware: Optional[bool] = None
    isolation_policy: Optional[bool] = None
    isolation_state: Optional[bool] = None
    lastseen: Optional[str] = None
    lastseen_error: Optional[str] = None
    lastseen_warning: Optional[str] = None
    machine_boottime: Optional[str] = None
    machine_serial: Optional[str] = None
    osbuild: Optional[int] = None
    osid: Optional[str] = None
    osmajor: Optional[int] = None
    osminor: Optional[int] = None
    osproducttype: Optional[str] = None
    ostype: Optional[str] = None
    osversion: Optional[str] = None
    pinned_version: Optional[str] = None
    policy: Optional[HarfanglabPolicy] = None
    producttype: Optional[str] = None
    quarantine_last_update: Optional[str] = None
    refresh_properties_status: Optional[str] = None
    refresh_quarantine_status: Optional[str] = None
    rollback_version: Optional[str] = None
    servicepack: Optional[str] = None
    starttime: Optional[str] = None
    status: Optional[str] = None
    subnet: Optional[HarfanglabSubnet] = None
    task_statuses: Optional[Dict[str, Any]] = None
    telemetry: Optional[Dict[str, Any]] = None
    telemetry_last_update: Optional[str] = None
    tenant: Optional[str] = None
    total_memory: Optional[int] = None
    uninstall_status: Optional[int] = None
    update_status: Optional[int] = None
    version: Optional[str] = None
    windows_groups_last_update: Optional[str] = None
    windows_users_last_update: Optional[str] = None

    class Config:
        extra = "allow"


class HarfanglabAgentPage(BaseModel):
    count: int = 0
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[HarfanglabAgent] = []

    class Config:
        extra = "allow"
