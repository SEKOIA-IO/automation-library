from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock

import pytest
import requests_mock

from aether_endpoint_security_api.trigger_security_events import EVENT_TYPES, AetherSecurityEventsTrigger


@pytest.fixture
def trigger(symphony_storage):
    trigger = AetherSecurityEventsTrigger()
    trigger.module.configuration = {
        "base_url": "https://api.usa.cloud.watchguard.com/",
        "account_id": "account-id",
        "access_id": "access-id",
        "access_secret": "password",
        "api_key": "api_key",
    }
    trigger.configuration = {"frequency": 604800}
    trigger.send_event = Mock()
    trigger.log = Mock()
    return trigger


def test_fetch_events(trigger):
    trigger._get_authorization = MagicMock(return_value="Bearer 123456")
    trigger._fetch_next_events = MagicMock(return_value=[])

    trigger._fetch_events()
    assert trigger.send_event.call_args_list == []
    assert len(trigger._fetch_next_events.call_args_list) == len(EVENT_TYPES)


def test_get_authorization_request_new_token_only_when_needed(trigger):
    url = f"{trigger.module.configuration['base_url']}/oauth/token"

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            json={
                "access_token": "123456",
                "expires_in": 10,
                "scope": "our-scope",
                "token_type": "bearer",
            },
        )

        token = trigger._get_authorization()
        assert token == "Bearer 123456"

        mock.post(
            url,
            json={
                "access_token": "78910",
                "expires_in": 10000,
                "scope": "our-scope",
                "token_type": "bearer",
            },
        )
        token = trigger._get_authorization()
        assert token == "Bearer 78910"

        mock.post(
            url,
            json={
                "access_token": "11111",
                "expires_in": 10000,
                "scope": "our-scope",
                "token_type": "bearer",
            },
        )

        token = trigger._get_authorization()
        assert token == "Bearer 78910"

        assert mock.call_count == 2


def test_fetch_next_exploits(trigger):
    event_type = 4
    url = (
        f"{trigger.module.configuration['base_url']}/rest/aether-endpoint-security/aether-mgmt/api/v1/accounts/"
        f"{trigger.module.configuration['account_id']}/securityevents/{event_type}/export/1"
    )
    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"

    with requests_mock.Mocker() as mock:
        trigger._get_authorization = MagicMock(return_value="Bearer 123456")

        message1 = {
            "event_id": 1796693,
            "event_type": 1,
            "date": (datetime.utcnow() + timedelta(minutes=1)).strftime(date_format),
            "host_name": "Myhostname",
            "path": "COMMON_APPDATA|\\safari-0x60dd82a3\\safari.exe",
            "action": 13,
            "hash": "5692CD3902FE3A9619F4B31A36643BAB",
            "risk": False,
            "protection_mode": 0,
            "detection_technology": None,
            "site_id": None,
            "exploit_technique": "Exploit/RunPE",
        }
        message2 = {
            "event_id": 1929394,
            "event_type": 1,
            "date": (datetime.utcnow() + timedelta(minutes=2)).strftime(date_format),
            "host_name": "Myhostname",
            "path": "COMMON_APPDATA|\\safari-0x60dd82a3\\safari.exe",
            "action": 13,
            "hash": "5692CD3902FE3A9619F4B31A36643BAB",
            "risk": False,
            "protection_mode": 0,
            "detection_technology": None,
            "site_id": None,
            "exploit_technique": "Exploit/RunPE",
        }
        mock.get(url, json={"data": [message1, message2]})

        expected_messages = []
        for message in [message1, message2]:
            expected_message = dict(message)
            expected_message["security_event_type"] = event_type
            expected_messages.append(expected_message)

        assert (
            trigger._fetch_next_events(
                last_message_date=datetime.utcnow().strftime(date_format),
                event_type=event_type,
            )
            == expected_messages
        )


def test_fetch_next_malware_urls(trigger):
    event_type = 13
    url = (
        f"{trigger.module.configuration['base_url']}/rest/aether-endpoint-security/aether-mgmt/api/v1/accounts/"
        f"{trigger.module.configuration['account_id']}/securityevents/{event_type}/export/1"
    )
    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"

    with requests_mock.Mocker() as mock:
        trigger._get_authorization = MagicMock(return_value="Bearer 123456")

        message1 = {
            "malware_category": 8,
            "path": "https://malicious.com",
            "number_of_occurrences": 8,
            "action": 2,
            "id": "52385e6a-d736-48ee-9c40-021155fe92ae",
            "site_name": "MySite",
            "host_name": "MyHostname",
            "device_type": 2,
            "security_event_date": (datetime.utcnow() + timedelta(minutes=1)).strftime(date_format),
            "ip_address": "1.2.3.4",
            "custom_group_folder_id": "40848101-2980-4709-ab0f-8c69eefe01de",
            "custom_group_folder_info": [
                {"name": "Root", "is_translatable": None, "type": 1},
                {"name": "PC", "is_translatable": None, "type": 2},
                {
                    "name": "PC - Lock + Update + Patching + Fw",
                    "is_translatable": None,
                    "type": 2,
                },
            ],
        }
        message2 = {
            "malware_category": 8,
            "path": "https://malicious.com",
            "number_of_occurrences": 8,
            "action": 2,
            "id": "57ca0608-a12b-4001-9e1c-a206fada8920",
            "site_name": "MySite",
            "host_name": "MyHostname",
            "device_type": 2,
            "security_event_date": (datetime.utcnow() + timedelta(minutes=2)).strftime(date_format),
            "ip_address": "1.2.3.4",
            "custom_group_folder_id": "40848101-2980-4709-ab0f-8c69eefe01de",
            "custom_group_folder_info": [
                {"name": "Root", "is_translatable": None, "type": 1},
                {"name": "PC", "is_translatable": None, "type": 2},
                {
                    "name": "PC - Lock + Update + Patching + Fw",
                    "is_translatable": None,
                    "type": 2,
                },
            ],
        }
        mock.get(url, json={"data": [message1, message2]})

        expected_messages = []
        for message in [message1, message2]:
            expected_message = dict(message)
            expected_message["security_event_type"] = event_type
            expected_messages.append(expected_message)

        assert (
            trigger._fetch_next_events(
                last_message_date=datetime.utcnow().strftime(date_format),
                event_type=event_type,
            )
            == expected_messages
        )


def test_fetch_next_intrusion_attempts(trigger):
    event_type = 15
    url = (
        f"{trigger.module.configuration['base_url']}/rest/aether-endpoint-security/aether-mgmt/api/v1/accounts/"
        f"{trigger.module.configuration['account_id']}/securityevents/{event_type}/export/1"
    )
    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"

    with requests_mock.Mocker() as mock:
        trigger._get_authorization = MagicMock(return_value="Bearer 123456")

        message1 = {
            "network_activity_type": 14,
            "id": "d63f1d21-86b1-45ce-8df5-6b9c7312a740",
            "site_name": "MySite",
            "host_name": "MyHost",
            "device_type": 3,
            "security_event_date": (datetime.utcnow() + timedelta(minutes=1)).strftime(date_format),
            "ip_address": "1.2.3.4",
            "custom_group_folder_id": "cae12752-c527-493b-b7a9-a71c19e74316",
            "custom_group_folder_info": [
                {"name": "Root", "is_translatable": True, "type": 1},
                {"name": "SRV", "is_translatable": None, "type": 2},
                {"name": "ALLSRV", "is_translatable": None, "type": 2},
                {"name": "ALLSRV Audit+FW", "is_translatable": None, "type": 2},
            ],
        }
        message2 = {
            "network_activity_type": 14,
            "id": "ee5accad-a0c9-452a-a6d0-b5b9fe8d8d23",
            "site_name": "MySite",
            "host_name": "MyHost",
            "device_type": 3,
            "security_event_date": (datetime.utcnow() + timedelta(minutes=2)).strftime(date_format),
            "ip_address": "1.2.3.4",
            "custom_group_folder_id": "9a6916aa-ad21-40f1-b6a5-3260556ae053",
            "custom_group_folder_info": [
                {"name": "Root", "is_translatable": True, "type": 1},
                {"name": "SRV", "is_translatable": None, "type": 2},
                {"name": "ALLSRV", "is_translatable": None, "type": 2},
                {"name": "ALLSRV Audit+FW", "is_translatable": None, "type": 2},
            ],
        }
        mock.get(url, json={"data": [message1, message2]})

        expected_messages = []
        for message in [message1, message2]:
            expected_message = dict(message)
            expected_message["security_event_type"] = event_type
            expected_messages.append(expected_message)

        assert (
            trigger._fetch_next_events(
                last_message_date=datetime.utcnow().strftime(date_format),
                event_type=event_type,
            )
            == expected_messages
        )


def test_filter_security_events(trigger):
    event_type = 1
    url = (
        f"{trigger.module.configuration['base_url']}/rest/aether-endpoint-security/aether-mgmt/api/v1/accounts/"
        f"{trigger.module.configuration['account_id']}/securityevents/{event_type}/export/1"
    )
    date_message = datetime.utcnow()
    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"

    with requests_mock.Mocker() as mock:
        trigger._get_authorization = MagicMock(return_value="Bearer 123456")

        message1 = {
            "security_event_date": date_message.strftime(date_format),
        }
        message2 = {
            "security_event_date": (date_message + timedelta(minutes=1)).strftime(date_format),
        }
        message3 = {
            "security_event_date": (date_message - timedelta(minutes=1)).strftime(date_format),
        }
        mock.get(url, json={"data": [message1, message2, message3]})

        expected_message = dict(message2)
        expected_message["security_event_type"] = event_type

        assert trigger._fetch_next_events(
            last_message_date=date_message.strftime(date_format),
            event_type=event_type,
        ) == [expected_message]


def test_fetch_next_events_with_no_response(trigger):
    event_type = 15
    url = (
        f"{trigger.module.configuration['base_url']}/rest/aether-endpoint-security/aether-mgmt/api/v1/accounts/"
        f"{trigger.module.configuration['account_id']}/securityevents/{event_type}/export/1"
    )
    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"

    with requests_mock.Mocker() as mock:
        trigger._get_authorization = MagicMock(return_value="Bearer 123456")
        mock.get(url, content=b"null")

        expected_messages = []

        assert (
            trigger._fetch_next_events(
                last_message_date=datetime.utcnow().strftime(date_format),
                event_type=event_type,
            )
            == expected_messages
        )


def test_fetch_next_events_with_empty_list(trigger):
    event_type = 15
    url = (
        f"{trigger.module.configuration['base_url']}/rest/aether-endpoint-security/aether-mgmt/api/v1/accounts/"
        f"{trigger.module.configuration['account_id']}/securityevents/{event_type}/export/1"
    )
    date_format = "%Y-%m-%dT%H:%M:%S.%fZ"

    with requests_mock.Mocker() as mock:
        trigger._get_authorization = MagicMock(return_value="Bearer 123456")
        mock.get(url, json={"data": []})

        expected_messages = []

        assert (
            trigger._fetch_next_events(
                last_message_date=datetime.utcnow().strftime(date_format),
                event_type=event_type,
            )
            == expected_messages
        )
