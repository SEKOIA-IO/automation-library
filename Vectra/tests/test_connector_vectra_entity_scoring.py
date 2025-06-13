from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import requests_mock
from pyrate_limiter import Duration, Limiter, RequestRate

from vectra_modules import VectraModule
from vectra_modules.client import ApiClient
from vectra_modules.connector_vectra_entity_scoring import VectraEntityScoringConnector, VectraEntityScoringConsumer
from vectra_modules.timestepper import TimeStepper


@pytest.fixture
def api_client():
    return ApiClient(base_url="https://example.portal.vectra.ai:443", client_id="user1234", client_secret="SECRET")


@pytest.fixture
def trigger(data_storage):
    module = VectraModule()
    module.configuration = {
        "base_url": "https://example.portal.vectra.ai:443",
        "client_id": "user1234",
        "client_secret": "SECRET",
    }

    trigger = VectraEntityScoringConnector(module=module, data_path=data_storage)
    trigger.configuration = {"intake_key": "INTAKE", "frequency": 60, "timedelta": 60, "start_time": 600}
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
        start_datetime = datetime(year=2025, month=6, day=16, hour=11, minute=24, second=25)
        end_datetime = start_datetime + timedelta(seconds=60)

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
            "https://example.portal.vectra.ai:443/api/v3.4/events/entity_scoring?type=account&event_timestamp_gte=2025-06-16T11%3A24%3A25.000000Z&event_timestamp_lte=2025-06-16T11%3A25%3A25.000000Z&limit=500",
            json=response_1,
        )

        consumer = VectraEntityScoringConsumer(connector=trigger, entity_type="account", client=api_client)
        events = list(consumer.fetch_events(start_datetime, end_datetime))

        assert len(events) == 1
