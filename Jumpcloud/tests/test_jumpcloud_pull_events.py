import os
import time
from datetime import datetime, timedelta, timezone
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from requests import Response

from jumpcloud_modules import JumpcloudDirectoryInsightsModule
from jumpcloud_modules.jumpcloud_pull_events import (
    FetchEventsException,
    JumpcloudDirectoryInsightsConnector,
)


@pytest.fixture
def fake_time():
    yield datetime(2022, 11, 5, 11, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def patch_datetime_now(fake_time):
    with patch("jumpcloud_modules.jumpcloud_pull_events.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield mock_datetime


@pytest.fixture
def trigger(data_storage, patch_datetime_now):
    module = JumpcloudDirectoryInsightsModule()
    trigger = JumpcloudDirectoryInsightsConnector(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "apikey": "myapikey",
        "base_url": "https://api.jumpcloud.com/",
    }
    trigger.configuration = {"intake_key": "intake_key"}
    yield trigger


@pytest.fixture
def message1():
    # flake8: noqa
    return {
        "id": "6407359ff5c3cc91c4d4608b",
        "mfa": False,
        "geoip": {
            "latitude": 48.8323,
            "timezone": "Europe/Paris",
            "longitude": 2.4075,
            "region_code": "75",
            "region_name": "Paris",
            "country_code": "FR",
            "continent_code": "EU",
        },
        "service": "sso",
        "@version": "1",
        "provider": "",
        "client_ip": "1.2.3.4",
        "timestamp": "2023-03-07T13:01:19.21859368Z",
        "useragent": {
            "os": "Windows",
            "name": "Chrome",
            "major": "110",
            "minor": "0",
            "patch": "0",
            "device": "Other",
            "os_full": "Windows 10",
            "os_name": "Windows",
            "version": "110.0.0.0",
            "os_major": "10",
            "os_version": "10",
        },
        "event_type": "sso_auth",
        "application": {
            "id": "5fad07f2b9f5414721b3d797",
            "name": "zoom",
            "sso_url": "https://sso.jumpcloud.com/saml2/zoom",
            "sso_type": "saml",
            "display_label": "Zoom",
        },
        "auth_context": {
            "system": {
                "id": "5ef4a50631ad0a2c1849c40a",
                "os": "Windows",
                "version": "11 Professionnel",
                "hostname": "JOHN-LAPTOP",
                "displayName": "JOHN-LAPTOP",
            },
            "auth_methods": {},
            "policies_applied": [
                {
                    "id": "",
                    "name": "Global Policy",
                    "metadata": {"action": "ALLOW", "resource_type": "APPLICATION"},
                }
            ],
        },
        "initiated_by": {
            "id": "5ee8dbcb03231715576d73cc",
            "type": "user",
            "username": "john.doe",
        },
        "organization": "5bf6defbdcd8233029e0c598",
        "error_message": "",
        "idp_initiated": False,
        "sso_token_success": True,
    }
    # flake8: qa


@pytest.fixture
def message2():
    # flake8: noqa
    return {
        "id": "B54A6D20-41F7-3FB0-84A6-01CFD7F1481F",
        "mfa": False,
        "geoip": {
            "latitude": 48.8323,
            "timezone": "Europe/Paris",
            "longitude": 2.4075,
            "region_code": "75",
            "region_name": "Paris",
            "country_code": "FR",
            "continent_code": "EU",
        },
        "outer": {"eap_type": None, "username": "jane.doe", "error_message": None},
        "service": "radius",
        "success": True,
        "@version": "1",
        "eap_type": "MSCHAPv2",
        "mfa_meta": {"type": ""},
        "username": "jane.doe",
        "auth_meta": {
            "auth_idp": "",
            "userid_type": "USERNAME",
            "user_cert_enabled": False,
            "device_cert_enabled": False,
            "user_password_enabled": False,
        },
        "auth_type": "EAP",
        "client_ip": "5.6.7.8",
        "timestamp": "2023-03-07T13:03:42Z",
        "event_type": "radius_auth_attempt",
        "initiated_by": {"type": "user", "username": "jane.doe"},
        "organization": "5bf6defbdcd8233029e0c598",
        "error_message": None,
        "nas_mfa_state": "",
    }
    # flake8: qa


def test_fetch_events(trigger, message1, message2):
    messages = [message1, message2]
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://api.jumpcloud.com/insights/directory/v1/events",
            status_code=200,
            json=messages,
            headers={"X-Result-Count": "2", "X-Limit": "1000"},
        )
        events = trigger.fetch_events()

        assert list(events) == [messages]
        assert trigger.from_date.isoformat() == "2023-03-07T13:03:43+00:00"


def test_fetch_events_with_pagination(trigger, message1, message2):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://api.jumpcloud.com/insights/directory/v1/events",
            [
                {
                    "status_code": 200,
                    "json": [message1],
                    "headers": {
                        "X-Result-Count": "1",
                        "X-Limit": "1",
                        "X-Search_after": '[1576181718000,"DZrPyW8BNsa9iKWoOm7h"]',
                    },
                },
                {
                    "status_code": 200,
                    "json": [message2],
                    "headers": {"X-Result-Count": "1", "X-Limit": "1000"},
                },
            ],
        )
        events = trigger.fetch_events()

        assert list(events) == [[message1], [message2]]
        assert trigger.from_date.isoformat() == "2023-03-07T13:03:43+00:00"


def test_next_batch_sleep_until_next_round(trigger, message1, message2):
    with patch("jumpcloud_modules.jumpcloud_pull_events.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://api.jumpcloud.com/insights/directory/v1/events",
            status_code=200,
            json=[message1, message2],
            headers={"X-Result-Count": "2", "X-Limit": "1000"},
        )
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_long_next_batch_should_not_sleep(trigger, message1, message2):
    with patch("jumpcloud_modules.jumpcloud_pull_events.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://api.jumpcloud.com/insights/directory/v1/events",
            status_code=200,
            json=[message1, message2],
            headers={"X-Result-Count": "2", "X-Limit": "1000"},
        )
        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0


@pytest.mark.skipif("{'JUMPCLOUD_BASE_URL', 'JUMPCLOUD_API_TOKEN'}.issubset(os.environ.keys()) == False")
def test_run_integration(data_storage):
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    with patch("jumpcloud_modules.jumpcloud_pull_events.datetime") as mock_datetime:
        mock_datetime.now.return_value = one_hour_ago
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        module = JumpcloudDirectoryInsightsModule()
        trigger = JumpcloudDirectoryInsightsConnector(module=module, data_path=data_storage)
        # mock the log function of trigger that requires network access to the api for reporting
        trigger.log = MagicMock()
        trigger.log_exception = MagicMock()
        trigger.push_events_to_intakes = MagicMock()
        trigger.module.configuration = {
            "base_url": os.environ["JUMPCLOUD_BASE_URL"],
            "apikey": os.environ["JUMPCLOUD_API_TOKEN"],
        }
        trigger.configuration = {"intake_key": "0123456789"}
        main_thread = Thread(target=trigger.run)
        main_thread.start()

        # wait few seconds
        time.sleep(60)
        trigger._stop_event.set()
        main_thread.join(timeout=60)

        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) > 0


def test_handle_response_error(data_storage):
    module = JumpcloudDirectoryInsightsModule()
    trigger = JumpcloudDirectoryInsightsConnector(module=module, data_path=data_storage)
    response = Response()
    response.status_code = 500
    response.reason = "Internal Error"
    with pytest.raises(FetchEventsException) as m:
        trigger._handle_response_error(response)

    assert (
        str(m.value)
        == "Request to Jumpcloud Directory Insights API to fetch events failed with status 500 - Internal Error"
    )
