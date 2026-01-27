import datetime
import json
from unittest.mock import Mock, patch

import pytest
import requests
import requests_mock
from sekoia_automation.asset_connector.models.ocsf.device import DeviceOCSFModel
from sekoia_automation.module import Module

from harfanglab.asset_connector.device_assets import HarfanglabAssetConnector


@pytest.fixture
def test_harfanglab_asset_connector(symphony_storage):
    module = Module()
    module.configuration = {
        "url": "https://example.com",
        "api_token": "fake_harfanglab_api_key",
    }

    test_harfanglab_asset_connector = HarfanglabAssetConnector(module=module, data_path=symphony_storage)
    test_harfanglab_asset_connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }

    test_harfanglab_asset_connector.log = Mock()
    test_harfanglab_asset_connector.log_exception = Mock()

    yield test_harfanglab_asset_connector


@pytest.fixture
def asset_first_object():
    return {
        "id": "3891597d-8696-4fc4-a260-b04880bdbd68",
        "group_count": None,
        "groups": [],
        "status": "offline",
        "policy": {
            "id": "eaa79dde-2c4c-4fb8-822b-20a0529ba6db",
            "tenant": None,
            "origin_stack": None,
            "macos_paths_muted_exact": [
                "/Applications/Avast.app/Contents/Backend/utils/com.avast.Antivirus.EndpointSecurity.app/Contents/MacOS/com.avast.Antivirus.EndpointSecurity.",
                "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/Metadata.framework/Versions/A/Support/corespotlightd",
            ],
            "macos_paths_muted_prefixes": [
                "/Applications/WithSecure/WithSecure Agent.app/",
                "/usr/libexec/",
            ],
            "macos_paths_muted_globs": [],
            "macos_paths_read_watched_exact": [
                "/private/etc/kcpassword",
                "/System/Library/Sandbox/rootless.conf",
            ],
            "macos_paths_read_watched_prefixes": [
                "/private/var/db/dslocal/nodes/Default/users/",
                "/Library/Keychains/",
                "/Network/Library/Keychains/",
            ],
            "macos_paths_read_watched_globs": [
                "/Users/*/Library/Application Support/Litecoin/wallets/**",
                "/Users/*/.ssh/*",
                "/Users/*/Library/Application Support/Microsoft Edge/*/**",
            ],
            "macos_paths_write_watched_exact": ["/Library/Application Support/com.apple.TCC/TCC.db"],
            "macos_paths_write_watched_prefixes": [
                "/System/Library/LaunchAgents/",
                "/Library/Scripts/",
            ],
            "macos_paths_write_watched_globs": [
                "/Users/*/Library/Preferences/**",
                "/Users/*/Library/LaunchAgents/**",
            ],
            "macos_paths_other_watched_exact": ["/Library/Application Support/com.apple.TCC/TCC.db"],
            "macos_paths_other_watched_prefixes": [
                "/System/Library/LaunchAgents/",
                "/Library/Scripts/",
            ],
            "macos_paths_other_watched_globs": [
                "/Users/*/Documents/**",
                "/private/var/folders/**/NSCreateObjectFileImageFromMemory-*",
            ],
            "windows_read_watched_paths": [
                "*\\PROGRAM FILES*",
                "*\\WINDOWS\\SYSTEM32\\CONFIG\\*",
            ],
            "windows_write_watched_paths": [
                "*\\PROGRAM FILES*",
                "*\\USERS\\DEFAULT\\NTUSER.DAT",
            ],
            "windows_registry_read_whitelist": [
                "HKU\\*\\SOFTWARE\\OPENSSH\\AGENT\\KEYS\\*",
            ],
            "windows_registry_read_blacklist": [],
            "linux_paths_other_watched_globs": [
                "/home/*/*",
                "/home/*/*/*",
                "/root/*",
                "/root/*/*",
                "/tmp/**",
                "/dev/shm/**",
            ],
            "use_driver": True,
            "use_process_block": False,
            "antivirus_policy_name": "GENSECEV_HarfangLab_AV_policy",
            "agent_auto_update": False,
            "agent_auto_forget": False,
            "agent_auto_forget_max_days": 1,
            "antivirus_profile": "d060dd94-fe99-4683-900e-f304e74fe97c",
            "antivirus_profile_name": "GENSECEV_HarfangLab_AV_policy",
            "local_endpoint_cache_size": 10240,
            "name": "GENSECEV_HarfangLab_EDR_policy",
            "description": "Used to automatically generate security events **DO NOT TOUCH**",
            "revision": 2,
            "sleeptime": 60,
            "sleepjitter": 10,
            "telemetry_process_state": "live",
            "telemetry_process_limit": False,
            "telemetry_process_limit_value": 1000,
            "telemetry_network_state": "live",
            "telemetry_network_limit": False,
            "telemetry_network_limit_value": 1000,
            "telemetry_log_state": "live",
            "telemetry_log_limit": False,
            "telemetry_log_limit_value": 1000,
            "telemetry_remotethread_state": "live",
            "telemetry_remotethread_limit": False,
            "telemetry_remotethread_limit_value": 1000,
            "telemetry_driverload_state": "live",
            "telemetry_driverload_limit": False,
            "telemetry_driverload_limit_value": 1000,
            "telemetry_powershell_state": "live",
            "telemetry_powershell_limit": False,
            "telemetry_powershell_limit_value": 1000,
            "telemetry_dns_resolution_state": "live",
            "telemetry_dns_resolution_limit": False,
            "telemetry_dns_resolution_limit_value": 1000,
            "telemetry_authentication_state": "live",
            "telemetry_authentication_limit": False,
            "telemetry_authentication_limit_value": 1000,
            "telemetry_usb_activity_state": "live",
            "telemetry_usb_activity_limit": False,
            "telemetry_usb_activity_limit_value": 1000,
            "telemetry_user_group_state": "live",
            "telemetry_user_group_limit": False,
            "telemetry_user_group_limit_value": 1000,
            "telemetry_registry_state": "on_alert",
            "telemetry_registry_limit": False,
            "telemetry_registry_limit_value": 1000,
            "telemetry_raw_device_access_state": "on_alert",
            "telemetry_raw_device_access_limit": False,
            "telemetry_raw_device_access_limit_value": 1000,
            "telemetry_named_pipe_state": "on_alert",
            "telemetry_named_pipe_limit": False,
            "telemetry_named_pipe_limit_value": 1000,
            "telemetry_raw_socket_creation_state": "on_alert",
            "telemetry_raw_socket_creation_limit": False,
            "telemetry_raw_socket_creation_limit_value": 1000,
            "telemetry_network_listen_state": "on_alert",
            "telemetry_network_listen_limit": False,
            "telemetry_network_listen_limit_value": 1000,
            "telemetry_process_access_state": "on_alert",
            "telemetry_process_access_limit": False,
            "telemetry_process_access_limit_value": 1000,
            "telemetry_process_tamper_state": "on_alert",
            "telemetry_process_tamper_limit": False,
            "telemetry_process_tamper_limit_value": 1000,
            "telemetry_url_request_state": "on_alert",
            "telemetry_url_request_limit": False,
            "telemetry_url_request_limit_value": 1000,
            "telemetry_wmi_event_state": "on_alert",
            "telemetry_wmi_event_limit": False,
            "telemetry_wmi_event_limit_value": 1000,
            "telemetry_file_state": "on_alert",
            "telemetry_file_limit": False,
            "telemetry_file_limit_value": 1000,
            "telemetry_file_download_state": "live",
            "telemetry_file_download_limit": False,
            "telemetry_file_download_limit_value": 1000,
            "telemetry_library_load_state": "on_alert",
            "telemetry_library_load_limit": False,
            "telemetry_library_load_limit_value": 1000,
            "telemetry_dotnet_library_state": "on_alert",
            "telemetry_alerts_limit": False,
            "telemetry_alerts_limit_value": 1000,
            "binary_download_enabled": False,
            "library_download_enabled": False,
            "thread_download_enabled": False,
            "telemetry_on_alert_enabled": False,
            "telemetry_on_alert_pre_alert_event_count": 5000,
            "telemetry_on_alert_post_alert_max_event_count": 5000,
            "telemetry_on_alert_post_alert_max_duration_secs": 600,
            "loglevel": "DEBUG",
            "sigma_mode": 1,
            "ioc_mode": 1,
            "ioc_scan_written_executable": False,
            "ioc_scan_libraries": False,
            "hlai_mode": 1,
            "hlai_skip_signed_ms": True,
            "hlai_skip_signed_others": False,
            "hlai_scan_libraries": True,
            "hlai_written_executable": True,
            "hlai_pdf": True,
            "hlai_minimum_level": "critical",
            "hlai_scripts_mode": 1,
            "hlai_scripts_minimum_level": "critical",
            "hibou_mode": 0,
            "hibou_skip_signed_ms": False,
            "hibou_skip_signed_others": False,
            "hibou_minimum_level": "critical",
            "yara_mode": 1,
            "yara_skip_signed_ms": True,
            "yara_skip_signed_others": False,
            "yara_scan_written_executable": True,
            "yara_scan_libraries_load": True,
            "ransomguard_mode": 1,
            "ransomguard_heuristic_mode": 1,
            "driverblock_mode": 1,
            "sidewatch_mode": 1,
            "use_isolation": True,
            "linux_use_isolation": True,
            "isolation_exclusions_revision": None,
            "windows_self_protection": True,
            "windows_self_protection_feature_hosts": False,
            "windows_self_protection_feature_safe_mode": True,
            "windows_self_protection_feature_firewall": True,
            "linux_self_protection": True,
            "linux_self_protection_feature_hosts": False,
            "audit_killswitch": False,
            "linux_startup_block": False,
            "feature_callback_tampering": True,
            "feature_process_tampering": True,
            "feature_live_process_heuristics": True,
            "feature_windows_filesystem_events": True,
            "feature_dse_tampering_mode": 1,
            "feature_event_stacktrace": True,
            "feature_ppl_antimalware": False,
            "agent_ui_enabled": False,
            "agent_ui_admin_message": None,
            "agent_ui_notification_scope": 2,
            "agent_ui_notification_level": 4,
            "synchronization_status": None,
            "sigma_ruleset": None,
            "yara_ruleset": None,
            "ioc_ruleset": None,
            "firewall_policy": None,
            "fim_policy": None,
            "antivirus_policy": "d060dd94-fe99-4683-900e-f304e74fe97c",
            "vulnerability_policy": None,
        },
        "tenant": None,
        "starttime": "2025-06-11T00:14:58.000000Z",
        "additional_info": {
            "additional_info1": "vagrant",
            "additional_info2": "wks",
            "additional_info3": None,
            "additional_info4": None,
        },
        "subnet": {
            "id": "35064b52-fa8a-4357-b21d-87ab8114add2",
            "gateway_ipaddress": "1.2.3.4",
            "gateway_macaddress": "55-55-00-22-33-22",
            "gateway_oui": None,
            "name": None,
        },
        "telemetry": None,
        "disk_count": 1,
        "encrypted_disk_count": 0,
        "domainname": "TestGROUP",
        "dnsdomainname": None,
        "hostname": "testhostaname1",
        "osmajor": 10,
        "osminor": 0,
        "osproducttype": "Windows 11 Enterprise Evaluation",
        "machine_serial": "0",
        "has_valid_password": True,
        "firstseen": "2025-06-11T00:15:06.454734Z",
        "lastseen": "2025-06-11T00:27:06.693963Z",
        "lastseen_warning": "2025-06-11T00:26:59.279324Z",
        "lastseen_error": "2025-06-11T00:27:29.279324Z",
        "version": "24.12.11-0bca88184713cdbb85eec416705f6a0baa07f518-dirty",
        "bitness": "x64",
        "distroid": None,
        "domain": None,
        "installdate": "2025-06-11 00:12:06+00:00",
        "ipaddress": "1.2.2.5",
        "ipmask": "255.255.255.0",
        "external_ipaddress": None,
        "osbuild": 22631,
        "osid": "00329-20000-00001-AA837",
        "ostype": "windows",
        "osversion": "10.0.22631",
        "producttype": "worktest",
        "servicepack": None,
        "total_memory": 4277866496,
        "cpu_count": 2,
        "cpu_frequency": 3408,
        "avg_cpu": 2.4,
        "avg_memory": 164448665,
        "avg_system_cpu": 14.4,
        "avg_system_memory": 3037852467,
        "avg_av_cpu": 0,
        "avg_av_memory": 80097280,
        "machine_boottime": "2025-06-11T00:13:20Z",
        "antivirus_name": "HarfangLab Antivirus",
        "antivirus_version": "6.3.23.0",
        "antivirus_rules_version": "108237",
        "antivirus_last_update_date": None,
        "antivirus_rules_last_update_date": "2025-06-10T18:04:36Z",
        "isolation_state": False,
        "isolation_policy": False,
        "driver_enabled": True,
        "driver_policy": False,
        "driver_version": "24.12.11",
        "is_ppl_antimalware": True,
        "rollback_version": None,
        "pinned_version": None,
        "task_statuses": None,
        "uninstall_status": 0,
        "update_status": 0,
        "refresh_properties_status": None,
        "windows_groups_last_update": None,
        "windows_users_last_update": None,
        "refresh_quarantine_status": None,
        "quarantine_last_update": None,
        "boot_loop_protection_end_date": None,
        "boot_loop_protection_boot_count": 1,
        "description": None,
        "effective_sigma_revision": 4156,
        "effective_yara_revision": 878,
        "effective_ioc_revision": 49,
        "effective_whitelist_revision": 2717,
        "effective_driver_blocklists_revision": 31,
        "telemetry_last_update": "2025-06-11T00:26:31.974049Z",
    }


@pytest.fixture
def asset_second_object():
    return {
        "id": "b39391f1-844c-4be6-a824-99a6908be30f",
        "group_count": None,
        "groups": [],
        "status": "offline",
        "policy": {
            "id": "3682b0ae-c95f-431e-9d4f-1efe01d38582",
            "tenant": None,
            "origin_stack": None,
            "macos_paths_muted_exact": [
                "/Applications/Avast.app/Contents/Backend/utils/com.avast.Antivirus.EndpointSecurity.app/Contents/MacOS/com.avast.Antivirus.EndpointSecurity.",
                "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/Metadata.framework/Versions/A/Support/corespotlightd",
            ],
            "macos_paths_muted_prefixes": [
                "/Applications/WithSecure/WithSecure Agent.app/",
                "/usr/libexec/",
            ],
            "macos_paths_muted_globs": [],
            "macos_paths_read_watched_exact": [
                "/private/etc/kcpassword",
                "/System/Library/Sandbox/rootless.conf",
            ],
            "macos_paths_read_watched_prefixes": [
                "/private/var/db/dslocal/nodes/Default/users/",
                "/Library/Keychains/",
                "/Network/Library/Keychains/",
            ],
            "macos_paths_read_watched_globs": [
                "/Users/*/Library/Application Support/Litecoin/wallets/**",
                "/Users/*/.ssh/*",
                "/Users/*/Library/Application Support/Microsoft Edge/*/**",
            ],
            "macos_paths_write_watched_exact": ["/Library/Application Support/com.apple.TCC/TCC.db"],
            "macos_paths_write_watched_prefixes": [
                "/System/Library/LaunchAgents/",
                "/Library/Scripts/",
            ],
            "macos_paths_write_watched_globs": [
                "/Users/*/Library/Preferences/**",
                "/Users/*/Library/LaunchAgents/**",
            ],
            "macos_paths_other_watched_exact": ["/Library/Application Support/com.apple.TCC/TCC.db"],
            "macos_paths_other_watched_prefixes": [
                "/System/Library/LaunchAgents/",
                "/Library/Scripts/",
            ],
            "macos_paths_other_watched_globs": [
                "/Users/*/Documents/**",
                "/private/var/folders/**/NSCreateObjectFileImageFromMemory-*",
            ],
            "windows_read_watched_paths": [
                "*\\PROGRAM FILES*",
                "*\\WINDOWS\\SYSTEM32\\CONFIG\\*",
            ],
            "windows_write_watched_paths": [
                "*\\PROGRAM FILES*",
                "*\\USERS\\DEFAULT\\NTUSER.DAT",
            ],
            "windows_registry_read_whitelist": [
                "HKU\\*\\SOFTWARE\\OPENSSH\\AGENT\\KEYS\\*",
            ],
            "windows_registry_read_blacklist": [],
            "linux_paths_other_watched_globs": [
                "/home/*/*",
                "/home/*/*/*",
                "/root/*",
                "/root/*/*",
                "/tmp/**",
                "/dev/shm/**",
            ],
            "use_driver": True,
            "use_process_block": False,
            "antivirus_policy_name": "GENSECEV_HarfangLab_AV_policy",
            "agent_auto_update": False,
            "agent_auto_forget": False,
            "agent_auto_forget_max_days": 1,
            "antivirus_profile": "d060dd94-fe99-4683-900e-f304e74fe97c",
            "antivirus_profile_name": "GENSECEV_HarfangLab_AV_policy",
            "local_endpoint_cache_size": 10240,
            "name": "GENSECEV_HarfangLab_EDR_policy",
            "description": "Used to automatically generate security events **DO NOT TOUCH**",
            "revision": 2,
            "sleeptime": 60,
            "sleepjitter": 10,
            "telemetry_process_state": "live",
            "telemetry_process_limit": False,
            "telemetry_process_limit_value": 1000,
            "telemetry_network_state": "live",
            "telemetry_network_limit": False,
            "telemetry_network_limit_value": 1000,
            "telemetry_log_state": "live",
            "telemetry_log_limit": False,
            "telemetry_log_limit_value": 1000,
            "telemetry_remotethread_state": "live",
            "telemetry_remotethread_limit": False,
            "telemetry_remotethread_limit_value": 1000,
            "telemetry_driverload_state": "live",
            "telemetry_driverload_limit": False,
            "telemetry_driverload_limit_value": 1000,
            "telemetry_powershell_state": "live",
            "telemetry_powershell_limit": False,
            "telemetry_powershell_limit_value": 1000,
            "telemetry_dns_resolution_state": "live",
            "telemetry_dns_resolution_limit": False,
            "telemetry_dns_resolution_limit_value": 1000,
            "telemetry_authentication_state": "live",
            "telemetry_authentication_limit": False,
            "telemetry_authentication_limit_value": 1000,
            "telemetry_usb_activity_state": "live",
            "telemetry_usb_activity_limit": False,
            "telemetry_usb_activity_limit_value": 1000,
            "telemetry_user_group_state": "live",
            "telemetry_user_group_limit": False,
            "telemetry_user_group_limit_value": 1000,
            "telemetry_registry_state": "on_alert",
            "telemetry_registry_limit": False,
            "telemetry_registry_limit_value": 1000,
            "telemetry_raw_device_access_state": "on_alert",
            "telemetry_raw_device_access_limit": False,
            "telemetry_raw_device_access_limit_value": 1000,
            "telemetry_named_pipe_state": "on_alert",
            "telemetry_named_pipe_limit": False,
            "telemetry_named_pipe_limit_value": 1000,
            "telemetry_raw_socket_creation_state": "on_alert",
            "telemetry_raw_socket_creation_limit": False,
            "telemetry_raw_socket_creation_limit_value": 1000,
            "telemetry_network_listen_state": "on_alert",
            "telemetry_network_listen_limit": False,
            "telemetry_network_listen_limit_value": 1000,
            "telemetry_process_access_state": "on_alert",
            "telemetry_process_access_limit": False,
            "telemetry_process_access_limit_value": 1000,
            "telemetry_process_tamper_state": "on_alert",
            "telemetry_process_tamper_limit": False,
            "telemetry_process_tamper_limit_value": 1000,
            "telemetry_url_request_state": "on_alert",
            "telemetry_url_request_limit": False,
            "telemetry_url_request_limit_value": 1000,
            "telemetry_wmi_event_state": "on_alert",
            "telemetry_wmi_event_limit": False,
            "telemetry_wmi_event_limit_value": 1000,
            "telemetry_file_state": "on_alert",
            "telemetry_file_limit": False,
            "telemetry_file_limit_value": 1000,
            "telemetry_file_download_state": "live",
            "telemetry_file_download_limit": False,
            "telemetry_file_download_limit_value": 1000,
            "telemetry_library_load_state": "on_alert",
            "telemetry_library_load_limit": False,
            "telemetry_library_load_limit_value": 1000,
            "telemetry_dotnet_library_state": "on_alert",
            "telemetry_alerts_limit": False,
            "telemetry_alerts_limit_value": 1000,
            "binary_download_enabled": False,
            "library_download_enabled": False,
            "thread_download_enabled": False,
            "telemetry_on_alert_enabled": False,
            "telemetry_on_alert_pre_alert_event_count": 5000,
            "telemetry_on_alert_post_alert_max_event_count": 5000,
            "telemetry_on_alert_post_alert_max_duration_secs": 600,
            "loglevel": "DEBUG",
            "sigma_mode": 1,
            "ioc_mode": 1,
            "ioc_scan_written_executable": False,
            "ioc_scan_libraries": False,
            "hlai_mode": 1,
            "hlai_skip_signed_ms": True,
            "hlai_skip_signed_others": False,
            "hlai_scan_libraries": True,
            "hlai_written_executable": True,
            "hlai_pdf": True,
            "hlai_minimum_level": "critical",
            "hlai_scripts_mode": 1,
            "hlai_scripts_minimum_level": "critical",
            "hibou_mode": 0,
            "hibou_skip_signed_ms": False,
            "hibou_skip_signed_others": False,
            "hibou_minimum_level": "critical",
            "yara_mode": 1,
            "yara_skip_signed_ms": True,
            "yara_skip_signed_others": False,
            "yara_scan_written_executable": True,
            "yara_scan_libraries_load": True,
            "ransomguard_mode": 1,
            "ransomguard_heuristic_mode": 1,
            "driverblock_mode": 1,
            "sidewatch_mode": 1,
            "use_isolation": True,
            "linux_use_isolation": True,
            "isolation_exclusions_revision": None,
            "windows_self_protection": True,
            "windows_self_protection_feature_hosts": False,
            "windows_self_protection_feature_safe_mode": True,
            "windows_self_protection_feature_firewall": True,
            "linux_self_protection": True,
            "linux_self_protection_feature_hosts": False,
            "audit_killswitch": False,
            "linux_startup_block": False,
            "feature_callback_tampering": True,
            "feature_process_tampering": True,
            "feature_live_process_heuristics": True,
            "feature_windows_filesystem_events": True,
            "feature_dse_tampering_mode": 1,
            "feature_event_stacktrace": True,
            "feature_ppl_antimalware": False,
            "agent_ui_enabled": False,
            "agent_ui_admin_message": None,
            "agent_ui_notification_scope": 2,
            "agent_ui_notification_level": 4,
            "synchronization_status": None,
            "sigma_ruleset": None,
            "yara_ruleset": None,
            "ioc_ruleset": None,
            "firewall_policy": None,
            "fim_policy": None,
            "antivirus_policy": "d060dd94-fe99-4683-900e-f304e74fe97c",
            "vulnerability_policy": None,
        },
        "tenant": None,
        "starttime": "2025-06-12T00:14:58.000000Z",
        "additional_info": {
            "additional_info1": "vagrant",
            "additional_info2": "wks",
            "additional_info3": None,
            "additional_info4": None,
        },
        "subnet": {
            "id": "b061fb24-a25b-479a-9293-0a4392fb7f4d",
            "gateway_ipaddress": "1.2.3.4",
            "gateway_macaddress": "55-55-00-22-33-22",
            "gateway_oui": None,
            "name": None,
        },
        "telemetry": None,
        "disk_count": 1,
        "encrypted_disk_count": 0,
        "domainname": "TestGROUP2",
        "dnsdomainname": None,
        "hostname": "testhostaname2",
        "osmajor": 10,
        "osminor": 0,
        "osproducttype": "Windows 11 Enterprise Evaluation",
        "machine_serial": "0",
        "has_valid_password": True,
        "firstseen": "2025-06-12T00:15:06.454734Z",
        "lastseen": "2025-06-12T00:27:06.693963Z",
        "lastseen_warning": "2025-06-12T00:26:59.279324Z",
        "lastseen_error": "2025-06-12T00:27:29.279324Z",
        "version": "24.12.11-0bca88184713cdbb85eec416705f6a0baa07f518-dirty",
        "bitness": "x64",
        "distroid": None,
        "domain": None,
        "installdate": "2025-06-12 00:12:06+00:00",
        "ipaddress": "1.2.2.5",
        "ipmask": "255.255.255.0",
        "external_ipaddress": None,
        "osbuild": 22631,
        "osid": "00329-20000-00001-AA837",
        "ostype": "windows",
        "osversion": "10.0.22631",
        "producttype": "worktest",
        "servicepack": None,
        "total_memory": 4277866496,
        "cpu_count": 2,
        "cpu_frequency": 3408,
        "avg_cpu": 2.4,
        "avg_memory": 164448665,
        "avg_system_cpu": 14.4,
        "avg_system_memory": 3037852467,
        "avg_av_cpu": 0,
        "avg_av_memory": 80097280,
        "machine_boottime": "2025-06-12T00:13:20Z",
        "antivirus_name": "HarfangLab Antivirus",
        "antivirus_version": "6.3.23.0",
        "antivirus_rules_version": "108237",
        "antivirus_last_update_date": None,
        "antivirus_rules_last_update_date": "2025-06-11T18:04:36Z",
        "isolation_state": False,
        "isolation_policy": False,
        "driver_enabled": True,
        "driver_policy": False,
        "driver_version": "24.12.11",
        "is_ppl_antimalware": True,
        "rollback_version": None,
        "pinned_version": None,
        "task_statuses": None,
        "uninstall_status": 0,
        "update_status": 0,
        "refresh_properties_status": None,
        "windows_groups_last_update": None,
        "windows_users_last_update": None,
        "refresh_quarantine_status": None,
        "quarantine_last_update": None,
        "boot_loop_protection_end_date": None,
        "boot_loop_protection_boot_count": 1,
        "description": None,
        "effective_sigma_revision": 4156,
        "effective_yara_revision": 878,
        "effective_ioc_revision": 49,
        "effective_whitelist_revision": 2717,
        "effective_driver_blocklists_revision": 31,
        "telemetry_last_update": "2025-06-12T00:26:31.974049Z",
    }


@pytest.fixture
def agent_endpoint_response(asset_first_object):
    return {"count": 1, "next": None, "previous": None, "results": [asset_first_object]}


def test_base_url(test_harfanglab_asset_connector):
    assert test_harfanglab_asset_connector.base_url == "https://example.com"


def test_extract_timestamp(test_harfanglab_asset_connector):
    asset = {"firstseen": "2023-10-01T12:00:00Z"}
    timestamp = test_harfanglab_asset_connector.extract_timestamp(asset)
    assert timestamp == datetime.datetime(2023, 10, 1, 12, 0, tzinfo=datetime.timezone.utc)
    assert timestamp.isoformat() == "2023-10-01T12:00:00+00:00"
    assert isinstance(timestamp, datetime.datetime)


def test_extract_os_type(test_harfanglab_asset_connector):
    asset = {"ostype": "windows"}
    os_type = test_harfanglab_asset_connector.extract_os_type(asset["ostype"])
    assert os_type == "WINDOWS"

    asset = {"ostype": "linux"}
    os_type = test_harfanglab_asset_connector.extract_os_type(asset["ostype"])
    assert os_type == "LINUX"

    asset = {"ostype": "macos"}
    os_type = test_harfanglab_asset_connector.extract_os_type(asset["ostype"])
    assert os_type == "MACOS"

    asset = {"ostype": "unknown"}
    os_type = test_harfanglab_asset_connector.extract_os_type(asset["ostype"])
    assert os_type == "UNKNOWN"


def test_map_fields(test_harfanglab_asset_connector, asset_first_object):
    mapped_device = test_harfanglab_asset_connector.map_fields(asset_first_object)

    # Test static fields
    assert isinstance(mapped_device, DeviceOCSFModel)
    assert mapped_device.activity_id == 2
    assert mapped_device.activity_name == "Collect"
    assert mapped_device.category_name == "Discovery"
    assert mapped_device.category_uid == 5
    assert mapped_device.class_name == "Asset"
    assert mapped_device.class_uid == 5001
    assert mapped_device.type_name == "Software Inventory Info: Collect"
    assert mapped_device.type_uid == 500102
    assert isinstance(mapped_device.time, float)

    # Test metadata fields
    assert mapped_device.metadata.product.name == "Harfanglab EDR"
    assert mapped_device.metadata.product.version == "24.12"
    assert mapped_device.metadata.version == "1.5.0"

    # Test device fields
    assert mapped_device.device.type_id == 2
    assert mapped_device.device.type == "Desktop"
    assert mapped_device.device.uid == asset_first_object["id"]
    assert mapped_device.device.os.name == asset_first_object["osproducttype"]
    assert mapped_device.device.os.type == asset_first_object["ostype"]
    assert mapped_device.device.os.type_id == 100
    assert mapped_device.device.hostname == asset_first_object["hostname"]


def test_map_fields_json_dumps(test_harfanglab_asset_connector, asset_first_object):
    mapped_device = test_harfanglab_asset_connector.map_fields(asset_first_object)
    json_data = mapped_device.model_dump()
    serialized_json = json.dumps(json_data)

    assert serialized_json
    assert json_data["device"]["os"]["type"] == "windows"
    assert json_data["device"]["os"]["type_id"] == 100
    assert json_data["device"]["type"] == "Desktop"
    assert json_data["device"]["type_id"] == 2


def test_fetch_devices(test_harfanglab_asset_connector, agent_endpoint_response, asset_first_object):
    with requests_mock.Mocker() as agent_request:
        agent_request.get(
            f"{test_harfanglab_asset_connector.base_url}/api/data/endpoint/Agent?ordering=firstseen&firstseen=2023-10-01T00%3A00%3A00%2B00%3A00&limit=1000",
            status_code=200,
            json=agent_endpoint_response,
        )

        from_date = "2023-10-01T00:00:00+00:00"
        devices = list(test_harfanglab_asset_connector._fetch_devices(from_date))

        assert len(devices) == 1
        assert devices[0] == [asset_first_object]


def test_fetch_devices_no_results(test_harfanglab_asset_connector):
    with requests_mock.Mocker() as agent_request:
        agent_request.get(
            f"{test_harfanglab_asset_connector.base_url}/api/data/endpoint/Agent?ordering=firstseen&firstseen=2023-10-01T00%3A00%3A00%2B00%3A00&limit=1000",
            status_code=200,
            json={"count": 0, "results": []},
        )

        from_date = "2023-10-01T00:00:00+00:00"
        devices = list(test_harfanglab_asset_connector._fetch_devices(from_date))

        assert len(devices) == 0


def test_build_network_interface(test_harfanglab_asset_connector, asset_first_object):
    network_interface = test_harfanglab_asset_connector.build_network_interface(asset_first_object)

    assert network_interface is not None
    assert network_interface.hostname == "testhostaname1"
    assert network_interface.ip == "1.2.2.5"
    assert network_interface.name is None
    assert network_interface.type == "Wired"
    assert network_interface.type_id == 1
    assert network_interface.uid == "35064b52-fa8a-4357-b21d-87ab8114add2"


def test_build_network_interface_no_data(test_harfanglab_asset_connector):
    asset_without_network = {"id": "test-id", "hostname": "test-host", "firstseen": "2023-10-01T12:00:00Z"}

    network_interface = test_harfanglab_asset_connector.build_network_interface(asset_without_network)
    assert network_interface is None


def test_build_enrichments(test_harfanglab_asset_connector, asset_first_object):
    enrichment = test_harfanglab_asset_connector.build_enrichments(asset_first_object)

    assert enrichment is not None
    assert enrichment.name == "compliance"
    assert enrichment.value == "hygiene"
    assert enrichment.data is not None

    # Test firewall status
    assert enrichment.data.Firewall_status == "Enabled"

    # Test encryption
    assert enrichment.data.Storage_encryption is not None
    assert enrichment.data.Storage_encryption.partitions["disk_0"] == "Disabled"

    # Users should be None
    assert enrichment.data.Users is None


def test_build_enrichments_no_firewall(test_harfanglab_asset_connector):
    asset_no_firewall = {
        "id": "test-id",
        "hostname": "test",
        "firstseen": "2023-10-01T12:00:00Z",
        "policy": {"windows_self_protection_feature_firewall": False},
        "disk_count": 0,
        "encrypted_disk_count": 0,
    }

    enrichment = test_harfanglab_asset_connector.build_enrichments(asset_no_firewall)
    assert enrichment is not None
    assert enrichment.data.Firewall_status == "Disabled"


def test_build_enrichments_mixed_encryption(test_harfanglab_asset_connector):
    asset_mixed_encryption = {
        "id": "test-id",
        "hostname": "test",
        "firstseen": "2023-10-01T12:00:00Z",
        "policy": {},
        "disk_count": 3,
        "encrypted_disk_count": 2,
    }

    enrichment = test_harfanglab_asset_connector.build_enrichments(asset_mixed_encryption)
    assert enrichment is not None
    assert enrichment.data.Storage_encryption.partitions["disk_0"] == "Enabled"
    assert enrichment.data.Storage_encryption.partitions["disk_1"] == "Enabled"
    assert enrichment.data.Storage_encryption.partitions["disk_2"] == "Disabled"


def test_build_enrichments_no_data(test_harfanglab_asset_connector):
    asset_no_data = {
        "id": "test-id",
        "hostname": "test",
        "firstseen": "2023-10-01T12:00:00Z",
        "disk_count": 0,
        "encrypted_disk_count": 0,
    }

    enrichment = test_harfanglab_asset_connector.build_enrichments(asset_no_data)
    assert enrichment is None


def test_build_device_extended_fields(test_harfanglab_asset_connector, asset_first_object):
    device = test_harfanglab_asset_connector.build_device(asset_first_object)

    # Test new fields
    assert device.domain == "TestGROUP"
    assert device.ip == "1.2.2.5"
    assert device.subnet == "255.255.255.0"
    assert device.is_managed is True
    assert device.is_trusted is True
    assert device.model == "worktest"
    assert device.vendor_name == "HarfangLab"
    assert device.desc is None

    # Test timestamps
    assert device.first_seen_time is not None
    assert device.last_seen_time is not None
    assert device.boot_time == 1749600800
    assert device.created_time is not None

    # Test network interfaces
    assert device.network_interfaces is not None
    assert len(device.network_interfaces) == 1
    assert device.network_interfaces[0].ip == "1.2.2.5"


def test_build_device_missing_optional_fields(test_harfanglab_asset_connector):
    minimal_asset = {
        "id": "test-id",
        "hostname": "test-host",
        "firstseen": "2023-10-01T12:00:00Z",
        "ostype": "linux",
        "osproducttype": "Ubuntu 22.04",
    }

    device = test_harfanglab_asset_connector.build_device(minimal_asset)

    assert device.uid == "test-id"


def test_iterate_devices(test_harfanglab_asset_connector, agent_endpoint_response, asset_first_object):
    with requests_mock.Mocker() as agent_request:
        agent_request.get(
            f"{test_harfanglab_asset_connector.base_url}/api/data/endpoint/Agent?ordering=firstseen&firstseen=2023-10-01T00%3A00%3A00%2B00%3A00&limit=1000",
            status_code=200,
            json=agent_endpoint_response,
        )

        with patch.object(
            type(test_harfanglab_asset_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: "2023-10-01T00:00:00+00:00"),
        ):
            devices = list(test_harfanglab_asset_connector.iterate_devices())

            assert len(devices) == 1
            assert len(devices[0]) == 1
            assert devices[0][0]["id"] == asset_first_object["id"]


def test_iterate_devices_no_results(test_harfanglab_asset_connector):
    with requests_mock.Mocker() as agent_request:
        agent_request.get(
            f"{test_harfanglab_asset_connector.base_url}/api/data/endpoint/Agent?ordering=firstseen&firstseen=2023-10-01T00%3A00%3A00%2B00%3A00&limit=1000",
            status_code=200,
            json={"count": 0, "results": []},
        )
        with patch.object(
            type(test_harfanglab_asset_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: "2023-10-01T00:00:00+00:00"),
        ):
            devices = list(test_harfanglab_asset_connector.iterate_devices())

            assert len(devices) == 0


def test_iterate_devices_pagination(test_harfanglab_asset_connector, asset_first_object, asset_second_object):
    agent_endpoint_response_page_1 = {
        "count": 2,
        "next": f"{test_harfanglab_asset_connector.base_url}/api/data/endpoint/Agent?ordering=firstseen&firstseen=2023-10-01T00%3A00%3A00%2B00%3A00&limit=1000&offset=1000",
        "previous": None,
        "results": [asset_first_object],
    }
    agent_endpoint_response_page_2 = {
        "count": 2,
        "next": None,
        "previous": f"{test_harfanglab_asset_connector.base_url}/api/data/endpoint/Agent?ordering=firstseen&firstseen=2023-10-01T00%3A00%3A00%2B00%3A00&limit=1000",
        "results": [asset_second_object],
    }

    with requests_mock.Mocker() as agent_request:
        agent_request.get(
            f"{test_harfanglab_asset_connector.base_url}/api/data/endpoint/Agent?ordering=firstseen&firstseen=2023-10-01T00%3A00%3A00%2B00%3A00&limit=1000",
            status_code=200,
            json=agent_endpoint_response_page_1,
        )
        agent_request.get(
            f"{test_harfanglab_asset_connector.base_url}/api/data/endpoint/Agent?ordering=firstseen&firstseen=2023-10-01T00%3A00%3A00%2B00%3A00&limit=1000&offset=1000",
            status_code=200,
            json=agent_endpoint_response_page_2,
        )

        with patch.object(
            type(test_harfanglab_asset_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: "2023-10-01T00:00:00+00:00"),
        ):
            devices = list(test_harfanglab_asset_connector.iterate_devices())

            assert len(devices) == 2
            assert devices[0][0]["id"] == asset_first_object["id"]
            assert devices[1][0]["id"] == asset_second_object["id"]
            assert test_harfanglab_asset_connector._latest_time == "2025-06-12T00:15:06.454735+00:00"


def test_iterate_devices_request_failure(test_harfanglab_asset_connector):
    with requests_mock.Mocker() as agent_request:
        agent_request.get(
            f"{test_harfanglab_asset_connector.base_url}/api/data/endpoint/Agent?ordering=firstseen&firstseen=2023-10-01T00%3A00%3A00%2B00%3A00&limit=1000",
            status_code=500,
        )

        with patch.object(
            type(test_harfanglab_asset_connector),
            "most_recent_date_seen",
            new_callable=lambda: property(lambda self: "2023-10-01T00:00:00+00:00"),
        ):
            with pytest.raises(requests.exceptions.HTTPError):
                list(test_harfanglab_asset_connector.iterate_devices())
