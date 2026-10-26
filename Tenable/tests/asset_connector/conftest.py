from datetime import UTC, datetime, timedelta

import pytest

DAY = 86400
T1 = int((datetime.now(UTC) - timedelta(days=5)).timestamp())
T2 = T1 + DAY
T3 = T2 + DAY
T5 = T3 + 2 * DAY


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _sdk_iso(ts: int) -> str:
    """Format written by the CheckpointTimestamp used up to 1.0.19."""
    return datetime.fromtimestamp(ts).astimezone(UTC).isoformat()


def _vuln(base: dict, finding_id: str, last_found: int, state: str = "OPEN", last_fixed: int | None = None) -> dict:
    vuln = {
        **base,
        "finding_id": finding_id,
        "state": state,
        "first_found": _iso(last_found),
        "last_found": _iso(last_found),
    }
    if last_fixed is not None:
        vuln["last_fixed"] = _iso(last_fixed)
    return vuln


@pytest.fixture
def asset_info():
    """Asset record in the Export Assets v2 chunk shape (what the connector caches)."""
    return {
        "id": "74a507c2-c885-41ee-a34d-e151c99e3f60",
        "has_agent": False,
        "operating_systems": ["Solaris 10 (sparc)"],
        "system_types": ["general-purpose"],
        "agent_names": [],
        "network": {
            "ipv4s": ["192.0.2.2"],
            "ipv6s": [],
            "fqdns": ["moxptgljp3d450f5.example.demo"],
            "mac_addresses": ["00:00:5E:00:53:4b"],
            "hostnames": ["moxptgljp3d450f5.example.demo"],
            "network_interfaces": [
                {
                    "ipv4s": ["192.0.2.2"],
                    "ipv6s": [],
                    "fqdns": ["moxptgljp3d450f5.example.demo"],
                    "mac_addresses": ["00:00:5E:00:53:4b"],
                    "name": "CATCH_ALL_INTERFACE",
                    "virtual": None,
                    "aliased": None,
                }
            ],
        },
        "timestamps": {
            "created_at": "2025-08-26T14:34:38.571Z",
            "updated_at": "2025-08-26T14:34:38.000Z",
            "first_seen": "2025-08-26T14:34:38.000Z",
            "last_seen": "2025-08-26T14:34:38.571Z",
        },
        "cloud": {},
    }


@pytest.fixture
def asset_details_payload():
    """Asset record in the Get Asset Details shape (returned by the fallback API call)."""
    return {
        "name": "moxptgljp3d450f5.example.demo",
        "id": "74a507c2-c885-41ee-a34d-e151c99e3f60",
        "has_agent": False,
        "created_at": "2025-08-26T14:34:38.571Z",
        "updated_at": "2025-08-26T14:34:38.000Z",
        "terminated_at": None,
        "deleted_at": None,
        "aes_score_v3": None,
        "acr_score_v3": 5.0,
        "first_seen": "2025-08-26T14:34:38.000Z",
        "last_seen": "2025-08-26T14:34:38.571Z",
        "last_scan_target": "192.0.2.2",
        "last_authentication_attempt_date": None,
        "last_authentication_success_date": None,
        "last_authenticated_scan_date": "2025-08-26T14:34:38.571Z",
        "last_licensed_scan_date": "2025-08-26T14:34:38.571Z",
        "last_scan_id": "3427421a-9476-e291-686f-8d60d7fc401892fd2478c88003fc",
        "last_schedule_id": "1c12e931-8a64-443e-9b0e-382c1ea32b70",
        "sources": [
            {"name": "NESSUS_SCAN", "first_seen": "2025-08-26T14:34:38.571Z", "last_seen": "2025-08-26T14:34:38.571Z"}
        ],
        "tags": [],
        "acr_score": None,
        "acr_drivers": None,
        "exposure_score": None,
        "scan_frequency": None,
        "interfaces": [
            {
                "ipv4": ["192.0.2.2"],
                "ipv6": [],
                "fqdn": ["moxptgljp3d450f5.example.demo"],
                "mac_address": ["00:00:5E:00:53:4b"],
                "name": "CATCH_ALL_INTERFACE",
                "virtual": None,
                "aliased": None,
            }
        ],
        "network_id": ["00000000-0000-0000-0000-000000000000"],
        "ipv4": ["192.0.2.2"],
        "ipv6": [],
        "fqdn": ["moxptgljp3d450f5.example.demo"],
        "mac_address": ["00:00:5E:00:53:4b"],
        "netbios_name": [],
        "operating_system": ["Solaris 10 (sparc)"],
        "system_type": ["general-purpose"],
        "tenable_uuid": ["103a8272187f4f0491c614fa8df962db"],
        "hostname": ["moxptgljp3d450f5.example.demo"],
        "agent_name": [],
        "bios_uuid": [],
        "aws_ec2_instance_id": [],
        "aws_ec2_instance_ami_id": [],
        "aws_owner_id": [],
        "aws_availability_zone": [],
        "aws_region": [],
        "aws_vpc_id": [],
        "aws_ec2_instance_group_name": [],
        "aws_ec2_instance_state_name": [],
        "aws_ec2_instance_type": [],
        "aws_subnet_id": [],
        "aws_ec2_product_code": [],
        "aws_ec2_name": [],
        "azure_vm_id": [],
        "azure_resource_id": [],
        "azure_subscription_id": [],
        "azure_resource_group": [],
        "azure_location": [],
        "azure_type": [],
        "gcp_project_id": [],
        "gcp_zone": [],
        "gcp_instance_id": [],
        "ssh_fingerprint": [],
        "mcafee_epo_guid": [],
        "mcafee_epo_agent_guid": [],
        "qualys_asset_id": [],
        "qualys_host_id": [],
        "servicenow_sysid": [],
        "installed_software": [],
        "bigfix_asset_id": [],
        "security_protection_level": None,
        "security_protections": [],
        "exposure_confidence_value": None,
    }


@pytest.fixture
def vulnerability():
    return {
        "asset": {
            "agent_uuid": "45bd0c2b59f347e49be93442699f4845",
            "device_type": "general-purpose",
            "fqdn": "s4r5r1zrzdbdxs0w.example.demo",
            "hostname": "s4r5r1zrzdbdxs0w.example.demo",
            "uuid": "d3fb3e2e-2f4a-4f4b-8f4a-1e2b3c4d5e6f",
        },
        "output": "\nRemote package installed : bind-libs-9.9.4-61.el7\nShould be                : bind-libs-9.9.4-74.el7_6.1\n\nRemote package installed : bind-license-9.9.4-61.el7\nShould be                : bind-license-9.9.4-74.el7_6.1\n\nRemote package installed : bind-utils-9.9.4-61.el7\nShould be                : bind-utils-9.9.4-74.el7_6.1\n\n",
        "plugin": {
            "bid": [125801],
            "checks_for_default_account": False,
            "checks_for_malware": False,
            "cpe": [
                "p-cpe:/a:centos:centos:bind-pkcs11",
                "p-cpe:/a:centos:centos:bind-pkcs11-utils",
                "cpe:/o:centos:centos:7",
                "p-cpe:/a:centos:centos:bind-license",
                "p-cpe:/a:centos:centos:bind-utils",
                "p-cpe:/a:centos:centos:bind-pkcs11-devel",
                "p-cpe:/a:centos:centos:bind-sdb-chroot",
                "p-cpe:/a:centos:centos:bind-devel",
                "p-cpe:/a:centos:centos:bind-libs-lite",
                "p-cpe:/a:centos:centos:bind",
                "p-cpe:/a:centos:centos:bind-sdb",
                "p-cpe:/a:centos:centos:bind-chroot",
                "p-cpe:/a:centos:centos:bind-lite-devel",
                "p-cpe:/a:centos:centos:bind-libs",
                "p-cpe:/a:centos:centos:bind-pkcs11-libs",
            ],
            "cvss3_base_score": 7.5,
            "cvss3_temporal_score": 6.5,
            "cvss3_temporal_vector": {
                "exploitability": "Unproven",
                "remediation_level": "Official Fix",
                "report_confidence": "Confirmed",
                "raw": "E:U/RL:O/RC:C",
            },
            "cvss3_vector": {
                "access_complexity": "Low",
                "access_vector": "Network",
                "availability_impact": "High",
                "confidentiality_impact": "None",
                "integrity_impact": "None",
                "raw": "AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
            },
            "cvss_base_score": 4.3,
            "cvss_temporal_score": 3.2,
            "cvss_temporal_vector": {
                "exploitability": "Unproven",
                "remediation_level": "Official Fix",
                "report_confidence": "Confirmed",
                "raw": "E:U/RL:OF/RC:C",
            },
            "cvss_vector": {
                "access_complexity": "Medium",
                "access_vector": "Network",
                "authentication": "None required",
                "availability_impact": "Partial",
                "confidentiality_impact": "None",
                "integrity_impact": "None",
                "raw": "AV:N/AC:M/Au:N/C:N/I:N/A:P",
            },
            "description": "An update for bind is now available for Red Hat Enterprise Linux 7.\n\nRed Hat Product Security has rated this update as having a security impact of Important. A Common Vulnerability Scoring System (CVSS) base score, which gives a detailed severity rating, is available for each vulnerability from the CVE link(s) in the References section.\n\nThe Berkeley Internet Name Domain (BIND) is an implementation of the Domain Name System (DNS) protocols. BIND includes a DNS server (named); a resolver library (routines for applications to use when interfacing with DNS); and tools for verifying that the DNS server is operating correctly.\n\nSecurity Fix(es) :\n\n* bind: Limiting simultaneous TCP clients is ineffective (CVE-2018-5743)\n\nFor more details about the security issue(s), including the impact, a CVSS score, acknowledgments, and other related information, refer to the CVE page(s) listed in the References section.",
            "exploit_available": False,
            "exploit_framework_canvas": False,
            "exploit_framework_core": False,
            "exploit_framework_d2_elliot": False,
            "exploit_framework_exploithub": False,
            "exploit_framework_metasploit": False,
            "exploitability_ease": "No known exploits are available",
            "exploited_by_malware": False,
            "exploited_by_nessus": False,
            "family": "CentOS Local Security Checks",
            "family_id": 38,
            "has_patch": True,
            "id": 125801,
            "in_the_news": False,
            "name": "CentOS 7 : bind (CESA-2019:1294)",
            "patch_publication_date": "2019-06-10T00:00:00Z",
            "modification_date": "2020-01-10T00:00:00Z",
            "publication_date": "2019-06-11T00:00:00Z",
            "risk_factor": "medium",
            "see_also": ["http://www.nessus.org/u?f35ea8cd"],
            "solution": "Update the affected bind packages.",
            "synopsis": "The remote CentOS host is missing one or more security updates.",
            "unsupported_by_vendor": False,
            "version": "1.5",
            "vuln_publication_date": "2019-10-09T00:00:00Z",
            "xrefs": [{"type": "CVE", "id": "2018-5743"}, {"type": "RHSA", "id": "2019:1294"}],
            "vpr": {
                "score": 3.6,
                "drivers": {
                    "age_of_vuln": {"lower_bound": 731},
                    "exploit_code_maturity": "UNPROVEN",
                    "cvss3_impact_score": 3.6,
                    "threat_intensity_last28": "VERY_LOW",
                    "threat_sources_last28": ["No recorded events"],
                    "product_coverage": "VERY_HIGH",
                },
                "updated": "2021-10-09T05:36:33Z",
            },
            "vpr_v2": {
                "score": 5.0,
                "vpr_percentile": 76.35,
                "vpr_severity": "MEDIUM",
                "exploit_probability": 0.002,
                "cve_id": "CVE-2018-5743",
                "exploit_code_maturity": "UNPROVEN",
                "on_cisa_kev": False,
                "in_the_news_intensity_last30": "VERY_LOW",
                "in_the_news_recency": "NO_RECORDED_EVENTS",
                "malware_observations_intensity_last30": "VERY_LOW",
                "malware_observations_recency": "NO_RECORDED_EVENTS",
            },
            "has_workaround": False,
            "cve": ["CVE-2018-5743"],
            "epss_score": 1.956,
            "type": "local",
        },
        "port": {"port": 0, "protocol": "TCP"},
        "scan": {
            "schedule_uuid": "1c12e931-8a64-443e-9b0e-382c1ea32b70",
            "started_at": "2025-08-26T14:34:38.571Z",
            "uuid": "3427421a-9476-e291-686f-8d60d7fc401892fd2478c88003fc",
            "target": "198.51.100.31",
        },
        "severity": "medium",
        "severity_id": 2,
        "severity_default_id": 2,
        "severity_modification_type": "NONE",
        "first_found": "2025-08-26T14:34:38.571Z",
        "last_found": "2025-08-26T14:34:38.571Z",
        "state": "OPEN",
        "indexed": "2025-08-26T14:35:07.817389Z",
        "source": "NESSUS",
        "finding_id": "0033592c-92f4-551c-bfc9-08490b970dc6",
    }
