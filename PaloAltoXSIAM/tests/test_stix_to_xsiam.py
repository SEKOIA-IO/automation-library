import pytest

from freezegun import freeze_time
from xsiam import XsiamModule
from xsiam.stix_to_xsiam import ActionArguments, STIXToXSIAMAction


@pytest.fixture
def action(data_storage):
    def fake_log_cb(message: str, level: str):
        print(message)
        return None

    module = XsiamModule()
    action = STIXToXSIAMAction(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    action.log = fake_log_cb
    action.module.configuration = {}
    return action


@freeze_time("2025-05-28")
def test_run():
    action = STIXToXSIAMAction()
    arguments = ActionArguments(
        stix_objects=[
            {
                "id": "indicator--1",
                "type": "indicator",
                "pattern": "[file:hashes.'SHA-256' = 'abc123']",
                "x_ic_observable_types": ["file"],
                "kill_chain_phases": [
                    {"kill_chain_name": "lockheed-martin-cyber-kill-chain", "phase_name": "delivery"},
                    {"kill_chain_name": "mitre-attack", "phase_name": "initial-access"},
                ],
                "valid_from": "2025-05-06T00:00:00Z",
                "valid_until": "2025-11-24T00:00:00Z",
                "x_inthreat_sources_refs": ["identity--d4e6daf6-6e06-4904-bf82-76d331ba491c"],
                "confidence": 70,
            },
            {
                "id": "indicator--2",
                "type": "indicator",
                "pattern": "[url:value = 'https://43.165.65.241/']",
                "x_ic_observable_types": ["url"],
                "kill_chain_phases": [
                    {"kill_chain_name": "lockheed-martin-cyber-kill-chain", "phase_name": "delivery"},
                    {"kill_chain_name": "mitre-attack", "phase_name": "exploitation"},
                ],
                "valid_from": "2025-05-06T00:00:00Z",
                "valid_until": "2025-11-24T00:00:00Z",
                "x_inthreat_sources_refs": ["identity--d4e6daf6-6e06-4904-bf82-76d331ba491c"],
                "confidence": 85,
            },
            {
                "id": "indicator--3",
                "type": "indicator",
                "pattern": "[file:hashes.MD5 = '22e933c9c5532d13fbcae3d9f2080c35' OR file:hashes.'SHA-1' = '6311eb48932a5544cbe3c2c2fe2b036231432bd4' OR file:hashes.'SHA-256' = '52a81e514d1113019f39273179f691379fbb78cd70a370aea22a00397cef5b99']",
                "x_ic_observable_types": ["file"],
                "kill_chain_phases": [
                    {"kill_chain_name": "lockheed-martin-cyber-kill-chain", "phase_name": "delivery"},
                    {"kill_chain_name": "mitre-attack", "phase_name": "initial-access"},
                ],
                "valid_from": "2025-05-06T00:00:00Z",
                "valid_until": "2025-11-24T00:00:00Z",
                "x_inthreat_sources_refs": ["identity--d4e6daf6-6e06-4904-bf82-76d331ba491c"],
                "x_inthreat_sources": [
                    {
                        "id": "indicator--3",
                        "name": "Test Source",
                        "x_ic_observable_types": ["truc"],
                        "confidence": 40,
                    }
                ],
                "confidence": 10,
            },
        ]
    )

    result = action.run(arguments=arguments)
    expected_result = [
        {
            "class": "indicator--1",
            "comment": "Valid from 2025-05-06T00:00:00Z AND STIX Pattern: " "[file:hashes.'SHA-256' = 'abc123']",
            "expiration_date": "1763942400",
            "indicator": "abc123",
            "reliability": "B",
            "reputation": "BAD",
            "severity": "MEDIUM",
            "type": "HASH",
            "validate": True,
            "vendors": [],
        },
        {
            "class": "indicator--2",
            "comment": "Valid from 2025-05-06T00:00:00Z AND STIX Pattern: [url:value = " "'https://43.165.65.241/']",
            "expiration_date": "1763942400",
            "indicator": "https://43.165.65.241/",
            "reliability": "A",
            "reputation": "BAD",
            "severity": "HIGH",
            "type": "DOMAIN_NAME",
            "validate": True,
            "vendors": [],
        },
        {
            "class": "indicator--3",
            "comment": "Valid from 2025-05-06T00:00:00Z AND STIX Pattern: [file:hashes.MD5 = "
            "'22e933c9c5532d13fbcae3d9f2080c35' OR file:hashes.'SHA-1' = "
            "'6311eb48932a5544cbe3c2c2fe2b036231432bd4' OR file:hashes.'SHA-256' = "
            "'52a81e514d1113019f39273179f691379fbb78cd70a370aea22a00397cef5b99']",
            "expiration_date": "1763942400",
            "indicator": "22e933c9c5532d13fbcae3d9f2080c35",
            "reliability": "E",
            "reputation": "BAD",
            "severity": "LOW",
            "type": "HASH",
            "validate": True,
            "vendors": [
                {
                    "reliability": "C",
                    "reputation": "BAD",
                    "vendor_name": "Test Source",
                },
            ],
        },
        {
            "class": "indicator--3",
            "comment": "Valid from 2025-05-06T00:00:00Z AND STIX Pattern: [file:hashes.MD5 = "
            "'22e933c9c5532d13fbcae3d9f2080c35' OR file:hashes.'SHA-1' = "
            "'6311eb48932a5544cbe3c2c2fe2b036231432bd4' OR file:hashes.'SHA-256' = "
            "'52a81e514d1113019f39273179f691379fbb78cd70a370aea22a00397cef5b99']",
            "expiration_date": "1763942400",
            "indicator": "52a81e514d1113019f39273179f691379fbb78cd70a370aea22a00397cef5b99",
            "reliability": "E",
            "reputation": "BAD",
            "severity": "LOW",
            "type": "HASH",
            "validate": True,
            "vendors": [
                {
                    "reliability": "C",
                    "reputation": "BAD",
                    "vendor_name": "Test Source",
                },
            ],
        },
    ]

    assert len(result) == 4
    assert result == expected_result
