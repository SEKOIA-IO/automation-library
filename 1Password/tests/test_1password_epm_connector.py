from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from onepassword_modules import OnePasswordModule
from onepassword_modules.connector_1password_epm import OnePasswordConnector, SignInAttemptsEndpoint


@pytest.fixture
def fake_time():
    yield datetime(2023, 12, 14, 0, 0, 1, tzinfo=timezone.utc)


@pytest.fixture
def patch_datetime_now(fake_time):
    with patch("onepassword_modules.connector_1password_epm.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield mock_datetime


@pytest.fixture
def trigger(data_storage, patch_datetime_now):
    module = OnePasswordModule()
    module.configuration = {"api_token": "myapikey", "base_url": "https://example.com"}

    trigger = OnePasswordConnector(module=module, data_path=data_storage)
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60}

    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()

    yield trigger


@pytest.fixture
def message_1():
    return {
        "cursor": "CURSOR_1",
        "has_more": True,
        "items": [
            {
                "uuid": "ABCDEF",
                "session_uuid": "GHIJK",
                "timestamp": "2024-09-06T14:16:35.017784891Z",
                "country": "FR",
                "category": "success",
                "type": "credentials_ok",
                "details": None,
                "target_user": {
                    "uuid": "LMNOPQ",
                    "name": "John",
                    "email": "john.doe@example.com",
                },
                "client": {
                    "app_name": "1Password for Web",
                    "app_version": "1817",
                    "platform_name": "Chrome",
                    "platform_version": "127.0.6533.99",
                    "os_name": "Linux",
                    "os_version": "6.10.5",
                    "ip_address": "1.2.3.4",
                },
                "location": {
                    "country": "FR",
                    "region": "Brittany",
                    "city": "Rennes",
                    "latitude": 48.11,
                    "longitude": -1.6744,
                },
            }
        ],
    }


@pytest.fixture
def message_2():
    return {
        "cursor": "CURSOR_2",
        "has_more": False,
        "items": [],
    }


def test_next_batch(trigger, message_1, message_2):
    trigger.from_date = 1645668000000
    worker = SignInAttemptsEndpoint(connector=trigger)

    with requests_mock.Mocker() as mock_requests, patch(
        "onepassword_modules.connector_1password_epm.time"
    ) as mock_time:
        mock_requests.post(
            "https://example.com/api/v1/signinattempts",
            [{"json": message_1}, {"json": message_2}],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        worker.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        mock_time.sleep.assert_called_once_with(44)


def test_next_batch_without_events(trigger, message_1, message_2):
    trigger.from_date = 1645668000000
    worker = SignInAttemptsEndpoint(connector=trigger)

    with requests_mock.Mocker() as mock_requests, patch(
        "onepassword_modules.connector_1password_epm.time"
    ) as mock_time:
        mock_requests.post(
            "https://example.com/api/v1/signinattempts",
            [{"json": message_2}],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        worker.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        mock_time.sleep.assert_called_once_with(44)
