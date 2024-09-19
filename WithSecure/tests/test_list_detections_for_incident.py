import pytest
import requests_mock

from withsecure import WithSecureModule
from withsecure.client.auth import API_AUTHENTICATION_URL
from withsecure.constants import API_LIST_DETECTION_URL
from withsecure.list_detections_for_incident import ActionArguments, ListDetectionForIncident


@pytest.fixture
def action(data_storage):
    def fake_log_cb(message: str, level: str):
        print(message)
        return None

    module = WithSecureModule()
    action = ListDetectionForIncident(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    action.log = fake_log_cb
    action.module.configuration = {
        "client_id": "fusion_000000000000000000000000",
        "secret": "0000000000000000000000000000000000000000000000000000000000000000",
    }
    return action


SINGLE_RESULT_ITEM = {
    "severity": "info",
    "privileges": "NORMAL_PRIVILEGES",
    "riskLevel": "info",
    "exePath": "%stestroot%\\system32",
    "createdTimestamp": "2024-05-06T11:41:46.716Z",
    "description": "test description",
    "pid": 996,
    "exeHash": "445f5f38365af88ec2",
    "deviceId": "0c3d6a05-613a",
    "detectionClass": "PROCESS",
    "activityContext": [
        {"type": "elevation", "status": "elevated"},
        {
            "eventCode": "21 (Remote Desktop Services: Session logon succeeded)",
            "sourceAddress": "1.2.3.4",
            "type": "test_services",
            "logonUsername": "testWorkstation\\testadmin",
        },
    ],
    "exeName": "testexename.exe",
    "name": "suspicious_remote_logon_session",
    "initialReceivedTimestamp": "2024-05-06T11:43:12Z",
    "incidentId": "341d0e1a-bf1d",
    "cmdl": "C:\\Windows\\system32\\testexename.exe -k DcomLaunch -p -s LSM",
    "username": "",
    "detectionId": "42ba511b-684a-4829",
}


def test_run_to_list_detections_for_an_incident(action):
    response_payload = {
        "items": [
            SINGLE_RESULT_ITEM,
        ]
    }

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
            API_LIST_DETECTION_URL,
            status_code=207,
            json=response_payload,
        )

        response = action.run(arguments=ActionArguments(target="e297cbf5-ba53-4e66-909c-6d87527c4e98"))

        assert isinstance(response, dict)
        assert response_payload["items"] == response["detections"]


def test_run_to_list_detections_for_an_incident_1(action):
    incident_id = "e297cbf5-ba53-4e66-909c-6d87527c4e98"
    response_payload_0 = {
        "items": [SINGLE_RESULT_ITEM, SINGLE_RESULT_ITEM],
        "nextAnchor": "next_anchor_0",
    }

    response_payload_1 = {
        "items": [SINGLE_RESULT_ITEM, SINGLE_RESULT_ITEM, SINGLE_RESULT_ITEM],
        "nextAnchor": "next_anchor_1",
    }

    response_payload_2 = {
        "items": [SINGLE_RESULT_ITEM, SINGLE_RESULT_ITEM, SINGLE_RESULT_ITEM, SINGLE_RESULT_ITEM],
    }

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
            API_LIST_DETECTION_URL + "?incidentId={0}".format(incident_id),
            complete_qs=True,
            status_code=207,
            json=response_payload_0,
        )
        mock_requests.get(
            API_LIST_DETECTION_URL + "?incidentId={0}&anchor=next_anchor_0".format(incident_id),
            complete_qs=True,
            status_code=207,
            json=response_payload_1,
        )
        mock_requests.get(
            API_LIST_DETECTION_URL + "?incidentId={0}&anchor=next_anchor_1".format(incident_id),
            complete_qs=True,
            status_code=207,
            json=response_payload_2,
        )

        response = action.run(arguments=ActionArguments(target="e297cbf5-ba53-4e66-909c-6d87527c4e98"))

        assert isinstance(response, dict)
        expected_items = response_payload_0["items"] + response_payload_1["items"] + response_payload_2["items"]

        assert expected_items == response["detections"]
