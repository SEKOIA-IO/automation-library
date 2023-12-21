import os
import pytest
import io
import json
from unittest.mock import patch

from zscaler.block_ioc import ZscalerBlockIOC, ZscalerUnBlockIOC, ZscalerPushIOCBlock, ZscalerListBLockIOC


@pytest.mark.skipif(
    "{'ZSCALER_BASE_URL', 'ZSCALER_API_KEY', 'ZSCALER_USERNAME', 'ZSCALER_PASSWORD'}"
    ".issubset(os.environ.keys()) == False"
)
def test_block_ioc_action_success():
    ZSCALER_TEST_TENANT_CONF = {
        "base_url": os.environ["ZSCALER_BASE_URL"],
        "api_key": os.environ["ZSCALER_API_KEY"],
        "username": os.environ["ZSCALER_USERNAME"],
        "password": os.environ["ZSCALER_PASSWORD"],
    }

    IOC_to_test = "megapromonet.com"
    action = ZscalerBlockIOC()
    action.module.configuration = ZSCALER_TEST_TENANT_CONF
    action.run({"IoC": IOC_to_test})

    verif = ZscalerListBLockIOC()
    verif.module.configuration = ZSCALER_TEST_TENANT_CONF
    response = verif.run()
    if IOC_to_test in response["blacklistUrls"]:
        response = "ok"
    assert response == "ok"


@pytest.mark.skipif(
    "{'ZSCALER_BASE_URL', 'ZSCALER_API_KEY', 'ZSCALER_USERNAME', 'ZSCALER_PASSWORD'}"
    ".issubset(os.environ.keys()) == False"
)
def test_push_ioc_action_success():
    ZSCALER_TEST_TENANT_CONF = {
        "base_url": os.environ["ZSCALER_BASE_URL"],
        "api_key": os.environ["ZSCALER_API_KEY"],
        "username": os.environ["ZSCALER_USERNAME"],
        "password": os.environ["ZSCALER_PASSWORD"],
    }

    # Define the content that the test should return when reading the file
    mocked_file_content = [
        {
            "valid_from": "2023-04-03T00:00:00Z",
            "x_ic_observable_types": ["ipv4-addr"],
            "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
            "object_marking_refs": ["marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"],
            "type": "indicator",
            "name": "77.91.78.118",
            "pattern": "[ipv4-addr:value = '77.91.78.118']",
            "kill_chain_phases": [
                {"kill_chain_name": "lockheed-martin-cyber-kill-chain", "phase_name": "command-and-control"},
                {"kill_chain_name": "mitre-attack", "phase_name": "command-and-control"},
            ],
            "spec_version": "2.1",
            "x_ic_impacted_sectors": [
                "identity--f910fbcc-9f6a-43db-a6da-980c224ab2dd",
                "identity--ecc48a52-4495-4f19-bc26-5ee51c176816",
                "identity--7a486419-cd78-4fcf-845d-261539b05450",
                "identity--39746349-9c5c-47bd-8f39-0aff658d8ee7",
                "identity--337c119c-6436-4bd8-80a5-dcec9bad3b2d",
                "identity--41070ab8-3181-4c01-9f75-c11df5fb1ca3",
                "identity--0ecc1054-756c-47d5-b7d2-640e5ba96513",
                "identity--26f07f1b-1596-41c1-b23b-8efc5b105792",
                "identity--8e1db464-79dd-44d5-bc20-6b305d879674",
                "identity--063ef3d7-3989-4cf6-95ee-6217c0ab367a",
                "identity--02efd9e3-b685-4a9b-98a0-6b4800ff1143",
                "identity--3a6e8c1b-db90-4f81-a677-a57d0ee7f055",
                "identity--275946eb-0b8a-4ffc-9297-56f2275ef0d2",
                "identity--499a1938-8f6f-4023-82a1-56400e42d697",
                "identity--ce0be931-0e2e-4e07-864c-b9b169da5f15",
                "identity--98bc4ec8-590f-49bf-b51e-b37228b6a4c0",
                "identity--dde50644-38ad-414a-bb6e-e097123558b5",
                "identity--62b911a8-bcab-4f31-91f0-af9cdf9b6d20",
                "identity--333fecdb-e60d-46e4-9f21-5424dccef693",
                "identity--721280f7-6c79-4c72-8e6c-2a8b17c11b32",
                "identity--99b2746a-3ece-422c-aa6e-833fbc28ebd5",
                "identity--b48266ac-b1b8-4d85-bf09-a56dd0462a14",
                "identity--de6d2cda-d23b-47b5-a869-1065044aefe0",
                "identity--39729d0f-a13b-4b24-abbe-0912a135aee7",
                "identity--ec9d3a40-064c-4ec0-b678-85f5623fc4f1",
            ],
            "x_inthreat_sources_refs": ["identity--556006db-0d85-4ecb-8845-89d40ae0d40f"],
            "x_ic_is_in_flint": False,
            "pattern_type": "stix",
            "revoked": False,
            "confidence": 100,
            "valid_until": "2023-04-29T00:00:00Z",
            "created": "2023-04-03T11:35:32.984278Z",
            "lang": "en",
            "modified": "2023-04-19T09:03:46.063418Z",
            "x_ic_impacted_locations": [
                "location--d6e38bb4-9e11-443f-b4f1-dc53068e15c4",
                "location--ce895300-199f-44fc-b6ad-f69ee6305ef8",
                "location--c2a15f03-dfc1-4659-a553-87770d75657d",
                "location--b2f21856-d558-4904-bbe7-f832af1adc2a",
                "location--b1111318-86ad-41be-a876-fec7c5b30c99",
                "location--a5e214d3-3584-4a96-ba86-e4f9bb07d148",
                "location--9966148d-0992-4f36-a617-db3f73e178aa",
                "location--97a9a8ca-47f2-4015-9bcd-c87d87d2a8a1",
                "location--092a468b-54e1-4199-9737-7268c84115bd",
                "location--1175a3bd-dd53-4a7e-9cdd-50743079025a",
                "location--1719933e-1ce5-43f6-ac2f-e9318b194235",
                "location--60c65af5-26b6-4a74-a785-45388295b7d3",
                "location--01d5f74a-2417-4c8e-a799-4eda69ac64d0",
                "location--387542b5-5690-489f-8420-7f68b0b9b828",
                "location--a678bc81-d40c-4455-9242-501de8cd0b02",
                "location--369e8445-c3b9-49f3-8dc8-a8df793513f0",
                "location--82b6e924-7bd8-4e19-9685-6863196fc60f",
                "location--dea6cc03-a488-48cf-b09b-7e9ca7ad9f7c",
                "location--b9c12531-454c-44a9-8317-63a975993e11",
                "location--867d31af-0ae0-4738-ba86-6353a0e5fb01",
                "location--05eae806-132b-4ce9-a307-5352c2b27d51",
                "location--9671f7eb-5b14-485e-befd-6fc3bdb38366",
            ],
            "x_ic_deprecated": False,
            "id": "indicator--f24eb993-4ece-47ff-90e1-fa3f87de85dc",
            "indicator_types": ["malicious-activity"],
            "x_ic_external_refs": ["indicator--731e9ebf-1569-4f2d-8df2-f0bb048a8c70"],
        }
    ]

    # Patch the open function to mock file reading
    with patch("zscaler.block_ioc.ZscalerPushIOCBlock.json_argument", return_value=mocked_file_content) as mock_open:
        action = ZscalerPushIOCBlock()
        action.module.configuration = ZSCALER_TEST_TENANT_CONF
        action.run({"stix_objects_path": "./stix_object.json"})

        verif = ZscalerListBLockIOC()
        verif.module.configuration = ZSCALER_TEST_TENANT_CONF
        response = verif.run()
        if "77.91.78.118" in response["blacklistUrls"]:
            response = "ok"
        assert response == "ok"


@pytest.mark.skipif(
    "{'ZSCALER_BASE_URL', 'ZSCALER_API_KEY', 'ZSCALER_USERNAME', 'ZSCALER_PASSWORD'}"
    ".issubset(os.environ.keys()) == False"
)
def test_unblock_ioc_action_success():
    ZSCALER_TEST_TENANT_CONF = {
        "base_url": os.environ["ZSCALER_BASE_URL"],
        "api_key": os.environ["ZSCALER_API_KEY"],
        "username": os.environ["ZSCALER_USERNAME"],
        "password": os.environ["ZSCALER_PASSWORD"],
    }

    IOC_to_test = "megapromonet.com"
    action = ZscalerUnBlockIOC()
    action.module.configuration = ZSCALER_TEST_TENANT_CONF
    action.run({"IoC": IOC_to_test})

    verif = ZscalerListBLockIOC()
    verif.module.configuration = ZSCALER_TEST_TENANT_CONF
    response = verif.run()
    if IOC_to_test not in response["blacklistUrls"]:
        response = "ok"
    assert response == "ok"
