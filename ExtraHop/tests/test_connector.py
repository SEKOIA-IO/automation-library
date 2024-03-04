from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from extrahop import ExtraHopModule
from extrahop.reveal_360_trigger import ExtraHopReveal360Connector


@pytest.fixture
def trigger(data_storage):
    module = ExtraHopModule()

    trigger = ExtraHopReveal360Connector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "base_url": "https://some-test-cloud.extrahop.com",
        "client_id": "user123",
        "client_secret": "some-secret",
    }
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60}
    trigger.get_last_timestamp = MagicMock()
    yield trigger


@pytest.fixture
def message_1():
    return {
        "id": 22222222222,
        "start_time": 1701379823296,
        "update_time": 1706720536009,
        "mod_time": 1706720577690,
        "title": "Deprecated SSL/TLS Versions",
        "description": "db1\\.example\\.org established an SSL/TLS connection with a deprecated version of SSL/TLS. SSL 2.0, SSL 3.0, and TLS 1.0 are deprecated because they are vulnerable to attacks.",
        "risk_score": 30,
        "type": "deprecated_ssl_tls_individual",
        "recommended_factors": [],
        "recommended": False,
        "categories": ["sec", "sec.hardening"],
        "properties": {"version": "TLSv1.0"},
        "participants": [
            {
                "role": "offender",
                "object_id": 33333333333,
                "object_type": "device",
                "object_value": "1.2.3.5",
                "hostname": "db1.example.org",
                "id": 2222,
                "external": False,
                "scanner_service": None,
            }
        ],
        "ticket_id": None,
        "assignee": None,
        "status": None,
        "resolution": None,
        "mitre_tactics": [],
        "mitre_techniques": [],
        "appliance_id": 3,
        "is_user_created": False,
    }


@pytest.fixture
def message_2():
    return {
        "id": 11111111111,
        "start_time": 1701270240000,
        "update_time": 1706720850000,
        "mod_time": 1706720877879,
        "title": "LLMNR Activity",
        "description": "[db3\\.example\\.org](#/metrics/devices/6e0cd9a20b0e46e39ce0eca0b71f195c.0e3faba10b8b0000/overview?from=1701270240&interval_type=DT&until=1706720940) sent Link-Local Multicast Name Resolution (LLMNR) requests that are part of an internal broadcast query to resolve a hostname. The LLMNR protocol is known to be vulnerable to attacks.",
        "risk_score": 30,
        "type": "llmnr_activity_individual",
        "recommended_factors": [],
        "recommended": False,
        "categories": ["sec", "sec.hardening"],
        "properties": {},
        "participants": [
            {
                "role": "offender",
                "object_id": 44444444444,
                "object_type": "device",
                "id": 3333,
                "external": False,
                "scanner_service": None,
            }
        ],
        "ticket_id": None,
        "assignee": None,
        "status": None,
        "resolution": None,
        "mitre_tactics": [],
        "mitre_techniques": [],
        "appliance_id": 3,
        "is_user_created": False,
    }


def test_fetch_events(trigger, message_1, message_2):
    trigger.from_date = 1645668000000
    messages = [message_1, message_2]
    with requests_mock.Mocker() as mock_requests, patch("extrahop.reveal_360_trigger.time") as mock_time:
        mock_requests.post(
            f"https://some-test-cloud.extrahop.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.post(
            "https://some-test-cloud.extrahop.com/api/v1/detections/search",
            [{"json": messages}, {"json": []}],
        )
        events = trigger.fetch_events()
        assert list(events) == [messages]


def test_next_batch(trigger, message_1, message_2):
    trigger.from_date = 1645668000000
    messages = [message_1, message_2]
    with requests_mock.Mocker() as mock_requests, patch("extrahop.reveal_360_trigger.time") as mock_time:
        mock_requests.post(
            f"https://some-test-cloud.extrahop.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.post(
            "https://some-test-cloud.extrahop.com/api/v1/detections/search",
            [{"json": messages}, {"json": []}],
        )
        # events = trigger.fetch_events()
        trigger.next_batch()
        assert trigger.push_events_to_intakes.call_count == 1


def test_clear_base_url_slash(data_storage, message_1, message_2):
    module = ExtraHopModule()

    trigger = ExtraHopReveal360Connector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "base_url": "https://some-test-cloud.extrahop.com/",
        "client_id": "user123",
        "client_secret": "some-secret",
    }
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60}
    trigger.get_last_timestamp = MagicMock()
    trigger.from_date = 1645668000000

    messages = [message_1, message_2]
    with requests_mock.Mocker() as mock_requests, patch("extrahop.reveal_360_trigger.time") as mock_time:
        mock_requests.post(
            f"https://some-test-cloud.extrahop.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.post(
            "https://some-test-cloud.extrahop.com/api/v1/detections/search",
            [{"json": messages}, {"json": []}],
        )
        # events = trigger.fetch_events()
        trigger.next_batch()
        assert trigger.push_events_to_intakes.call_count == 1


def test_clear_base_url_without_scheme(data_storage, message_1, message_2):
    module = ExtraHopModule()

    trigger = ExtraHopReveal360Connector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "base_url": "some-test-cloud.extrahop.com",
        "client_id": "user123",
        "client_secret": "some-secret",
    }
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60}
    trigger.get_last_timestamp = MagicMock()
    trigger.from_date = 1645668000000

    messages = [message_1, message_2]
    with requests_mock.Mocker() as mock_requests, patch("extrahop.reveal_360_trigger.time") as mock_time:
        mock_requests.post(
            f"https://some-test-cloud.extrahop.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.post(
            "https://some-test-cloud.extrahop.com/api/v1/detections/search",
            [{"json": messages}, {"json": []}],
        )
        # events = trigger.fetch_events()
        trigger.next_batch()
        assert trigger.push_events_to_intakes.call_count == 1
