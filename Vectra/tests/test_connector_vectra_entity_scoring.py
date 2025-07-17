from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
import requests_mock

from vectra_modules import VectraModule
from vectra_modules.client import ApiClient
from vectra_modules.connector_vectra_entity_scoring import VectraEntityScoringConnector, VectraEntityScoringConsumer


@pytest.fixture
def fake_time():
    yield datetime(2022, 11, 5, 11, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def patch_datetime_now(fake_time):
    with patch("vectra_modules.connector_vectra_entity_scoring.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        mock_datetime.fromtimestamp = lambda ts: datetime.fromtimestamp(ts)
        yield mock_datetime


@pytest.fixture
def api_client():
    return ApiClient(base_url="https://example.portal.vectra.ai:443", client_id="user1234", client_secret="SECRET")


@pytest.fixture
def trigger(data_storage, patch_datetime_now):
    module = VectraModule()
    module.configuration = {
        "base_url": "https://example.portal.vectra.ai:443",
        "client_id": "user1234",
        "client_secret": "SECRET",
    }

    trigger = VectraEntityScoringConnector(module=module, data_path=data_storage)
    trigger.configuration = {
        "intake_key": "INTAKE",
        "frequency": 60,
        "timedelta": 60,
        "start_time": 600,
        "chunk_size": 500,
    }
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()
    return trigger


@pytest.fixture
def response_1():
    return {
        "events": [
            {
                "id": 1111,
                "entity_id": 333,
                "name": "O365:john.doe@example.org",
                "breadth_contrib": 0,
                "importance": 1,
                "type": "account",
                "is_prioritized": False,
                "severity": "Low",
                "urgency_score": 30,
                "velocity_contrib": 0,
                "attack_rating": 1,
                "active_detection_types": ["M365 Unusual eDiscovery Search"],
                "category": "ACCOUNT SCORING",
                "url": "https://test.uw2.portal.vectra.ai/accounts/333",
                "event_timestamp": "2024-08-13T20:43:59Z",
                "last_detection": {
                    "id": 444,
                    "type": "M365 Unusual eDiscovery Search",
                    "url": "https://test.uw2.portal.vectra.ai/detections/444",
                },
            },
        ],
        "next_checkpoint": 1234,
        "remaining_count": 0,
    }


def test_fetch_events(trigger, api_client, response_1):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri(
            "POST",
            "https://example.portal.vectra.ai:443/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.register_uri(
            "GET",
            "https://example.portal.vectra.ai:443/api/v3.4/events/entity_scoring?type=account&limit=500&event_timestamp_gte=2022-10-11T11%3A59%3A59.000000Z",
            json=response_1,
        )

        consumer = VectraEntityScoringConsumer(connector=trigger, entity_type="account", client=api_client)
        events = list(consumer.fetch_events())

        assert len(events) == 1


def test_start_consumers(trigger, api_client):
    with patch("vectra_modules.connector_vectra_entity_scoring.VectraEntityScoringConsumer.start") as mock_start:
        consumers = trigger.start_consumers(api_client)
        assert consumers is not None
        assert "host" in consumers
        assert "account" in consumers

        assert mock_start.called


def test_supervise_consumers(trigger):
    with patch("vectra_modules.connector_vectra_entity_scoring.VectraEntityScoringConsumer.start") as mock_start:
        consumers = {
            "host": Mock(**{"is_alive.return_value": False, "running": True}),
            "something_else": None,
            "account": Mock(**{"is_alive.return_value": False, "running": False}),
        }
        trigger.supervise_consumers(consumers, api_client)
        assert mock_start.call_count == 2


def test_stop_consumers(trigger):
    consumers = {
        "host": Mock(**{"is_alive.return_value": False}),
        "account": Mock(**{"is_alive.return_value": False}),
        "something_new": Mock(**{"is_alive.return_value": True}),
    }

    trigger.stop_consumers(consumers)

    assert consumers["something_new"] is not None
    assert consumers["something_new"].stop.called
