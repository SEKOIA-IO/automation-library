import json

import pytest
import requests
import requests_mock

from withsecure import WithSecureModule
from withsecure.client.auth import API_AUTHENTICATION_URL
from withsecure.constants import API_LIST_DEVICES_URL
from withsecure.list_devices_action import ListDevicesAction


@pytest.fixture
def action(data_storage):
    def fake_log_cb(message: str, level: str):
        print(message)
        return None

    module = WithSecureModule()
    action = ListDevicesAction(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    action.log = fake_log_cb
    action.module.configuration = {
        "client_id": "fusion_000000000000000000000000",
        "secret": "0000000000000000000000000000000000000000000000000000000000000000",
    }
    return action


@pytest.fixture
def aws_computer_device() -> dict:
    return {
        "profileName": "WithSecure™ Server",
        "biosVersion": "1.0",
        "malwareDbVersion": "2023-05-20_07",
        "lastUser": "EC2AMAZ-BOG9C6F\\Administrator",
        "dnsAddress": "EC2AMAZ-BOG9C6F",
        "firewallState": "disabledByGpoOk",
        "subscription": {
            "productVariant": "serverprotection_premium_rdr",
            "name": "EDR and EPP for Servers Premium",
            "key": "0000-0000-0000-0000-0000",
        },
        "systemDriveTotalSize": 32210153472,
        "clientVersion": "23.4",
        "type": "computer",
        "dataguardState": "disabled",
        "winsAddress": "EC2AMAZ-BOG9C6F",
        "protectionStatusOverview": "allOk",
        "macAddresses": "0E-E3-1C-E3-00-00",
        "protectionStatus": "protected",
        "company": {"name": "Sekoia.io", "id": "00000000-0000-0000-0000-000000000000"},
        "patchOverallState": "importantUpdatesInstalled",
        "id": "e297cbf5-ba53-4e66-909c-000000000000",
        "publicInternet": False,
        "userPrincipalName": "",
        "computerModel": "t3.large",
        "profileState": "upToDate",
        "serialNumber": "ec298270-651b-f728-d6be-000000000000",
        "os": {"name": "Windows Server 2022", "version": "21H2", "endOfLife": False},
        "publicIpAddress": "15.188.57.73",
        "edrIncidents": {"riskSevere": 0, "riskHigh": 0, "riskMedium": 0},
        "physicalMemoryFree": 7496605696,
        "malwareState": "enabled",
        "discEncryptionEnabled": False,
        "physicalMemoryTotalSize": 8482484224,
        "patchLastScanTimestamp": "2023-05-20T07:23:58Z",
        "statusUpdateTimestamp": "2023-05-20T13:15:16.550Z",
        "registrationTimestamp": "2023-05-17T06:42:03.062Z",
        "systemDriveFreeSpace": 14072868864,
        "applicationControlState": "disabled",
        "name": "EC2AMAZ-BOG9C6F",
        "online": True,
        "ipAddresses": "172.31.40.211/20",
        "currentUserAdmin": True,
        "malwareDbUpdateTimestamp": "2023-05-20T12:34:21Z",
        "deviceControlState": "disabled",
    }


@pytest.fixture
def aws_computer_device1() -> dict:
    return {
        "profileName": "WithSecure™ Server",
        "biosVersion": "1.0",
        "malwareDbVersion": "2023-05-20_07",
        "lastUser": "EC2AMAZ-1111111\\Administrator",
        "dnsAddress": "EC2AMAZ-1111111",
        "firewallState": "disabledByGpoOk",
        "subscription": {
            "productVariant": "serverprotection_premium_rdr",
            "name": "EDR and EPP for Servers Premium",
            "key": "0000-0000-0000-0000-0000",
        },
        "systemDriveTotalSize": 32210153472,
        "clientVersion": "23.4",
        "type": "computer",
        "dataguardState": "disabled",
        "winsAddress": "EC2AMAZ-1111111",
        "protectionStatusOverview": "allOk",
        "macAddresses": "0E-E3-1C-E3-00-00",
        "protectionStatus": "protected",
        "company": {"name": "Sekoia.io", "id": "00000000-0000-0000-0000-000000000000"},
        "patchOverallState": "importantUpdatesInstalled",
        "id": "e297cbf5-ba53-4e66-909c-111111111111",
        "publicInternet": False,
        "userPrincipalName": "",
        "computerModel": "t3.large",
        "profileState": "upToDate",
        "serialNumber": "ec298270-651b-f728-d6be-000000000000",
        "os": {"name": "Windows Server 2022", "version": "21H2", "endOfLife": False},
        "publicIpAddress": "15.188.57.73",
        "edrIncidents": {"riskSevere": 0, "riskHigh": 0, "riskMedium": 0},
        "physicalMemoryFree": 7496605696,
        "malwareState": "enabled",
        "discEncryptionEnabled": False,
        "physicalMemoryTotalSize": 8482484224,
        "patchLastScanTimestamp": "2023-05-20T07:23:58Z",
        "statusUpdateTimestamp": "2023-05-20T13:15:16.550Z",
        "registrationTimestamp": "2023-05-17T06:42:03.062Z",
        "systemDriveFreeSpace": 14072868864,
        "applicationControlState": "disabled",
        "name": "EC2AMAZ-1111111",
        "online": True,
        "ipAddresses": "172.31.40.211/20",
        "currentUserAdmin": True,
        "malwareDbUpdateTimestamp": "2023-05-20T12:34:21Z",
        "deviceControlState": "disabled",
    }


def test_run_with_single_device_and_no_organization_id(action, aws_computer_device):
    response_payload = {"items": [aws_computer_device]}

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=200,
            json={
                "access_token": "eHcMH7mMmrVK2vaTMnqwRk8ono4yVeBMO6/x2L887as",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.get(
            API_LIST_DEVICES_URL,
            status_code=200,
            json=response_payload,
        )

        assert action.run(arguments={}) == {
            "devices": [{"id": "e297cbf5-ba53-4e66-909c-000000000000", "type": "computer", "name": "EC2AMAZ-BOG9C6F"}]
        }


def test_run_with_organization_id(action, aws_computer_device):
    response_payload = {"items": [aws_computer_device]}
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=200,
            json={
                "access_token": "eHcMH7mMmrVK2vaTMnqwRk8ono4yVeBMO6/x2L887as",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.get(
            API_LIST_DEVICES_URL,
            status_code=200,
            json=response_payload,
        )
        assert action.run(arguments={"organization_id": "13a8b22c-05bc-4fbd-bda4-ad8a4f0009d9"}) == {
            "devices": [{"id": "e297cbf5-ba53-4e66-909c-000000000000", "type": "computer", "name": "EC2AMAZ-BOG9C6F"}]
        }


def test_run_with_multiple_page(action, aws_computer_device, aws_computer_device1):
    def custom_matcher(request: requests.Request):
        if request.url == API_AUTHENTICATION_URL:
            resp = requests.Response()
            resp._content = json.dumps(
                {
                    "access_token": "eHcMH7mMmrVK2vaTMnqwRk8ono4yVeBMO6/x2L887as",
                    "token_type": "Bearer",
                    "expires_in": 1799,
                }
            ).encode()
            resp.status_code = 200

            return resp
        elif request.url.startswith(API_LIST_DEVICES_URL) and "anchor" not in request.url:
            resp = requests.Response()
            resp._content = json.dumps({"items": [aws_computer_device], "nextAnchor": "next-anchor1"}).encode()
            resp.status_code = 200
            return resp
        elif request.url.startswith(API_LIST_DEVICES_URL) and "next-anchor1" in request.url:
            resp = requests.Response()
            resp._content = json.dumps({"items": [aws_computer_device1]}).encode()
            resp.status_code = 200
            return resp
        return None

    with requests_mock.Mocker() as mock_requests:
        mock_requests.add_matcher(custom_matcher)

        assert action.run(arguments={}) == {
            "devices": [
                {"id": "e297cbf5-ba53-4e66-909c-000000000000", "type": "computer", "name": "EC2AMAZ-BOG9C6F"},
                {"id": "e297cbf5-ba53-4e66-909c-111111111111", "type": "computer", "name": "EC2AMAZ-1111111"},
            ]
        }
