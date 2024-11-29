from unittest.mock import MagicMock

import pytest
import requests_mock

from sentinelone_module.iocs.create_iocs import CreateIOCsAction, CreateIOCsArguments


@pytest.fixture(scope="module")
def arguments():
    return CreateIOCsArguments(
        sekoia_base_url="https://app.sekoia.io", stix_objects_path="./stix_path.txt", filters=None
    )


def test_get_valid_indicators(symphony_storage, sentinelone_module):
    create_iocs_action = CreateIOCsAction(module=sentinelone_module, data_path=symphony_storage)
    stix_objects = [
        {
            "id": "vulnerability--00000000000000000000000",
            "type": "vulnerability",
            "created_by_ref": "identity--00000000000000000000000",
            "created": "2024-09-05T06:06:12.967809Z",
            "modified": "2024-09-05T13:02:01.64122Z",
            "revoked": False,
            "external_references": [{"source_name": "cve", "external_id": "CVE-2024-0000"}],
            "object_marking_refs": ["marking-definition--00000000000000000000000"],
            "lang": "en",
            "spec_version": "2.1",
            "x_inthreat_sources_refs": ["identity--000000000000000000000"],
            "x_ic_is_in_flint": False,
            "x_ic_deprecated": False,
            "name": "CVE-2024-0000",
            "description": "test description",
            "x_ic_external_refs": ["vulnerability--7b0d71ed-afb6-5242-84cd-945cff68ea87"],
        },
        {
            "id": "indicator--f05f2077-0000-4726-9690-00000000000",
            "type": "indicator",
            "created_by_ref": "identity--357447d7-0000-4ce1-b7fa-000000000",
            "created": "2024-09-05T12:30:58.097336Z",
            "modified": "2024-09-05T12:30:58.097352Z",
            "revoked": False,
            "object_marking_refs": ["marking-definition--000000000000000"],
            "confidence": 70,
            "lang": "en",
            "spec_version": "2.1",
            "x_inthreat_sources_refs": ["identity--000000000000000"],
            "x_ic_is_in_flint": False,
            "x_ic_impacted_sectors": [],
            "x_ic_impacted_locations": [],
            "x_ic_deprecated": False,
            "name": "[file:hashes.'SHA-256' = '88d0dcf9d74bd5fd9a01b974d1e98c3598fa7917daa844b605be2a9656c2a0f7' OR file:hashes.MD5 = '418e26285f51fa8a57df9e34f734df48' OR file:hashes.'SHA-1' = '382129a6834c702afeaa53ff5f2ad10a3ad49c0c']",
            "pattern": "[file:hashes.'SHA-256' = '88d0dcf9d74bd5fd9a01b974d1e98c3598fa7917daa844b605be2a9656c2a0f7' OR file:hashes.MD5 = '418e26285f51fa8a57df9e34f734df48' OR file:hashes.'SHA-1' = '382129a6834c702afeaa53ff5f2ad10a3ad49c0c']",
            "valid_from": "2024-09-05T00:00:00Z",
            "valid_until": "2025-09-01T00:00:00Z",
            "kill_chain_phases": [
                {"kill_chain_name": "lockheed-martin-cyber-kill-chain", "phase_name": "installation"},
                {"kill_chain_name": "mitre-attack", "phase_name": "persistence"},
            ],
            "pattern_type": "stix",
            "indicator_types": ["malicious-activity"],
            "x_ic_observable_types": ["file"],
            "x_ic_external_refs": ["indicator--000000000000000"],
        },
    ]

    indicators = create_iocs_action.get_valid_indicators(stix_objects)

    assert len(indicators["valid"]) == 1
    assert indicators["valid"][0].creationTime
    assert indicators["valid"][0].validUntil
    assert indicators["valid"][0].source == "Sekoia.io"


def test_create_iocs(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    create_iocs_action = CreateIOCsAction(module=sentinelone_module, data_path=symphony_storage)
    stix_objects = [
        {
            "id": "vulnerability--00000000000000000000000",
            "type": "vulnerability",
            "created_by_ref": "identity--00000000000000000000000",
            "created": "2024-09-05T06:06:12.967809Z",
            "modified": "2024-09-05T13:02:01.64122Z",
            "revoked": False,
            "external_references": [{"source_name": "cve", "external_id": "CVE-2024-0000"}],
            "object_marking_refs": ["marking-definition--00000000000000000000000"],
            "lang": "en",
            "spec_version": "2.1",
            "x_inthreat_sources_refs": ["identity--000000000000000000000"],
            "x_ic_is_in_flint": False,
            "x_ic_deprecated": False,
            "name": "CVE-2024-0000",
            "description": "test description",
            "x_ic_external_refs": ["vulnerability--7b0d71ed-afb6-5242-84cd-945cff68ea87"],
        },
        {
            "id": "indicator--f05f2077-0000-4726-9690-00000000000",
            "type": "indicator",
            "created_by_ref": "identity--357447d7-0000-4ce1-b7fa-000000000",
            "created": "2024-09-05T12:30:58.097336Z",
            "modified": "2024-09-05T12:30:58.097352Z",
            "revoked": False,
            "object_marking_refs": ["marking-definition--000000000000000"],
            "confidence": 70,
            "lang": "en",
            "spec_version": "2.1",
            "x_inthreat_sources_refs": ["identity--000000000000000"],
            "x_ic_is_in_flint": False,
            "x_ic_impacted_sectors": [],
            "x_ic_impacted_locations": [],
            "x_ic_deprecated": False,
            "name": "[file:hashes.'SHA-256' = '88d0dcf9d74bd5fd9a01b974d1e98c3598fa7917daa844b605be2a9656c2a0f7' OR file:hashes.MD5 = '418e26285f51fa8a57df9e34f734df48' OR file:hashes.'SHA-1' = '382129a6834c702afeaa53ff5f2ad10a3ad49c0c']",
            "pattern": "[file:hashes.'SHA-256' = '88d0dcf9d74bd5fd9a01b974d1e98c3598fa7917daa844b605be2a9656c2a0f7' OR file:hashes.MD5 = '418e26285f51fa8a57df9e34f734df48' OR file:hashes.'SHA-1' = '382129a6834c702afeaa53ff5f2ad10a3ad49c0c']",
            "valid_from": "2024-09-05T00:00:00Z",
            "valid_until": "2025-09-01T00:00:00Z",
            "kill_chain_phases": [
                {"kill_chain_name": "lockheed-martin-cyber-kill-chain", "phase_name": "installation"},
                {"kill_chain_name": "mitre-attack", "phase_name": "persistence"},
            ],
            "pattern_type": "stix",
            "indicator_types": ["malicious-activity"],
            "x_ic_observable_types": ["file"],
            "x_ic_external_refs": ["indicator--000000000000000"],
        },
    ]

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/threat-intelligence/iocs",
            json={
                "data": [
                    {
                        "patternType": "string",
                        "campaignNames": [{"type": "string"}],
                        "description": "string",
                        "metadata": "string",
                        "scopeId": "225494730938493804",
                        "value": "string",
                        "validUntil": "2018-02-27T04:49:26.257525Z",
                        "externalId": "string",
                        "method": "EQUALS",
                        "type": "DNS",
                        "category": [
                            {
                                "type": "string",
                                "x-nullable": True,
                                "description": "The categories of the Threat Intelligence indicator, e.g.  the malware type associated with the IOC",
                            }
                        ],
                        "scope": "group",
                        "labels": [{"type": "string"}],
                        "pattern": "string",
                        "source": "string",
                        "reference": [
                            {
                                "type": "string",
                                "x-nullable": True,
                                "description": "External reference associated with the Threat Intelligence indicator",
                            }
                        ],
                        "uuid": "string",
                        "originalRiskScore": "integer",
                        "severity": "integer",
                        "creationTime": "2018-02-27T04:49:26.257525Z",
                        "name": "string",
                        "creator": "string",
                        "malwareNames": [{"type": "string"}],
                        "uploadTime": "2018-02-27T04:49:26.257525Z",
                        "mitreTactic": [{"type": "string"}],
                        "updatedAt": "2018-02-27T04:49:26.257525Z",
                        "threatActorTypes": [{"type": "string"}],
                        "intrusionSets": [{"type": "string"}],
                        "batchId": "string",
                        "threatActors": [{"type": "string"}],
                    },
                ]
            },
        )

        create_iocs_action.json_argument = MagicMock(return_value=stix_objects)

        assert len(create_iocs_action.run(arguments)["indicators"]) == 1
        assert create_iocs_action.run(arguments)["indicators"][0]["updatedAt"] == "2018-02-27T04:49:26.257525Z"
