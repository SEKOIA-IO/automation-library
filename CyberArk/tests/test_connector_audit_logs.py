from unittest.mock import MagicMock, patch

import pytest
import requests
import requests_mock

from cyberark_modules import CyberArkModule
from cyberark_modules.client.auth import AuthorizationFailedException
from cyberark_modules.connector_audit_logs import CyberArkAuditLogsConnector, CyberArkAuditLogsConnectorConfiguration


@pytest.fixture
def trigger(data_storage):
    module = CyberArkModule()
    module.configuration = {
        "auth_base_url": "https://example.id.cyberark.cloud",
        "login_name": "login",
        "password": "qwerty",
        "application_id": "MyApp1",
    }

    trigger = CyberArkAuditLogsConnector(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "api_base_url": "https://example.cyberark.cloud",
        "api_key": "APIKEY1234",
        "intake_key": "intake_key",
    }
    yield trigger


@pytest.fixture
def events1():
    return [
        {
            "uuid": "20fced38-7a82-4e32-8ca7-3ca599dac97b",
            "tenantId": "c1ff0b56-1b0a-4409-9226-80bee50ef8cf",
            "timestamp": 1739921924719,
            "username": "PVWAGWUser",
            "applicationCode": "PAM",
            "auditCode": "PAM00088",
            "auditType": "Info",
            "action": "Set Password",
            "userId": "PVWAGWUser",
            "source": "PVWAAPP",
            "actionType": "Password",
            "component": "Vault",
            "serviceName": "Privilege Cloud",
            "accessMethod": None,
            "accountId": "",
            "target": "",
            "command": None,
            "sessionId": None,
            "message": "",
            "customData": {"PAM": {"new_target": "", "target": ""}},
            "cloudProvider": None,
            "cloudWorkspacesAndRoles": [],
            "cloudIdentities": None,
            "cloudAssets": None,
            "safe": "",
            "accountName": "",
            "targetPlatform": "",
            "targetAccount": "",
            "identityType": None,
        }
    ]


@pytest.fixture
def message1(events1):
    return {
        "data": events1,
        "paging": {"cursor": {"cursorRef": "secondPageCursor"}},
    }


@pytest.fixture
def message2():
    return {"data": [], "paging": {"cursor": {"cursorRef": "secondPageCursor"}}}


def test_fetch_events(trigger, message1, message2, events1):
    trigger.from_date = 1739921924000

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=200,
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/createQuery",
            status_code=200,
            json={"cursorRef": "cursorRef"},
        )

        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/results",
            [
                {"status_code": 200, "json": message1},
                {"status_code": 200, "json": message2},
            ],
        )
        events = trigger.fetch_events()

        assert list(events) == [events1]
        assert trigger.from_date == 1739921924719


def test_next_batch_sleep_until_next_round(trigger, message1, message2):
    with patch("cyberark_modules.connector_audit_logs.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=200,
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/createQuery",
            status_code=200,
            json={"cursorRef": "cursorRef"},
        )

        mock_requests.post(
            "https://example.cyberark.cloud/api/audits/stream/results",
            [
                {"status_code": 200, "json": message1},
                {"status_code": 200, "json": message2},
            ],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_authorization_error(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=400,
            json={"error": "Auth error", "code": "<CODE>", "description": "Some description"},
        )
        with pytest.raises(AuthorizationFailedException):
            trigger.next_batch()


def test_authorization_error_without_details(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=400,
            json={},
        )
        with pytest.raises(AuthorizationFailedException):
            trigger.next_batch()


def test_network_error(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.id.cyberark.cloud/oauth2/token/MyApp1",
            status_code=500,
            json={"error": "Auth error", "code": "<CODE>", "description": "Some description"},
        )
        with pytest.raises(requests.HTTPError):
            trigger.next_batch()
