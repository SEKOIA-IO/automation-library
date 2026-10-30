"""Anonymised InsightVM records shared by the asset connector tests."""

from rapid7_insightvm.asset_connector.models import (
    Rapid7Asset,
    Rapid7Finding,
    Rapid7Vulnerability,
    VulnerabilitySummary,
)

ASSET_ID = "00000000-0000-0000-0000-000000000000-default-asset-1"
OTHER_ASSET_ID = "00000000-0000-0000-0000-000000000000-default-asset-2"
VULN_ID = "openssh-cve-2024-6387"
OTHER_VULN_ID = "linux-grub-missing-passwd"
THIRD_VULN_ID = "database-open-access"

NOW_T = "2026-10-28T11:00:00Z"  # NOW - CLOUD_SYNC_DELAY
ASSESSED = "2026-10-13T15:04:28.719Z"


def make_finding(vuln_id: str = VULN_ID, status: str = "VULNERABLE_EXPL", **overrides) -> dict:
    finding = {
        "check_id": None,
        "first_found": "2026-09-22T15:35:48Z",
        "key": "",
        "last_found": ASSESSED,
        "nic": None,
        "port": 22,
        "proof": "<p><ul><li>Running SSH service</li></ul></p>",
        "protocol": "TCP",
        "reintroduced": None,
        "solution_id": "openssh-upgrade-latest",
        "status": status,
        "vulnerability_id": vuln_id,
    }
    finding.update(overrides)
    return finding


def make_asset(asset_id: str = ASSET_ID, new=None, same=None, remediated=None, **overrides) -> dict:
    asset = {
        "assessed_for_vulnerabilities": True,
        "host_name": "host-01.example.com",
        "id": asset_id,
        "ip": "192.0.2.10",
        "mac": "00:00:5E:00:53:01",
        "last_assessed_for_vulnerabilities": ASSESSED,
        "os_description": "Ubuntu Linux 24.04",
        "os_family": "Linux",
        "os_name": "Linux",
        "os_system_name": "Ubuntu Linux",
        "os_type": "",
        "os_vendor": "Ubuntu",
        "risk_score": 1707.4,
        "tags": [{"name": "Example-Site", "type": "SITE"}],
        "type": "guest",
        "unique_identifiers": [{"id": "00000000-0000-0000-0000-000000000001", "source": "dmidecode"}],
        "new": new or [],
        "remediated": remediated or [],
    }
    if same is not None:
        asset["same"] = same
    asset.update(overrides)
    return asset


def make_vulnerability(vuln_id: str = VULN_ID, **overrides) -> dict:
    vulnerability = {
        "added": "2024-07-01T00:00:00Z",
        "categories": "Network,OpenSSH",
        "cves": "CVE-2024-6387",
        "cvss_v2_score": 9.3,
        "cvss_v2_vector": "(AV:N/AC:M/Au:N/C:C/I:C/A:C)",
        "cvss_v3_score": 8.1,
        "cvss_v3_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "description": "A signal handler race condition was found in sshd.",
        "id": vuln_id,
        "links": [
            {"href": "http://nvd.nist.gov/vuln/detail/CVE-2024-6387", "id": "CVE-2024-6387", "source": "cve"},
            {"href": None, "id": "EUVD-2024-0001", "source": "euvd"},
        ],
        "risk_score": 845.4,
        "severity": "critical",
        "title": "OpenSSH: CVE-2024-6387",
    }
    vulnerability.update(overrides)
    return vulnerability


def finding(vuln_id: str = VULN_ID, status: str = "VULNERABLE_EXPL", **overrides) -> Rapid7Finding:
    return Rapid7Finding.model_validate(make_finding(vuln_id, status, **overrides))


def asset(asset_id: str = ASSET_ID, **overrides) -> Rapid7Asset:
    return Rapid7Asset.model_validate(make_asset(asset_id, **overrides))


def vulnerability(vuln_id: str = VULN_ID, **overrides) -> Rapid7Vulnerability:
    return Rapid7Vulnerability.model_validate(make_vulnerability(vuln_id, **overrides))


def summary(vuln_id: str = VULN_ID, **overrides) -> VulnerabilitySummary:
    return VulnerabilitySummary.from_vulnerability(vulnerability(vuln_id, **overrides))
