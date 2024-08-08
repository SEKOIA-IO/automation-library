"""Tests for Trellix EDR connector."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aioresponses import aioresponses
from dateutil.parser import isoparse
from faker import Faker
from orjson import orjson

from client.schemas.attributes.edr_affectedhosts import EdrAffectedhostAttributes
from client.schemas.attributes.edr_alerts import EdrAlertAttributes
from client.schemas.attributes.edr_detections import EdrDetectionAttributes
from client.schemas.attributes.edr_threats import EdrThreatAttributes
from client.schemas.token import HttpToken, Scope
from client.schemas.trellix_response import TrellixResponse
from connectors.trellix_edr_connector import TrellixEdrConnector
from connectors.trellix_epo_connector import TrellixModule


@pytest.fixture
def connector(
    module: TrellixModule,
    symphony_storage: Path,
    session_faker: Faker,
    mock_push_data_to_intakes: AsyncMock,
) -> TrellixEdrConnector:
    """
    Fixture for TrellixEdrConnector.

    Args:
        module: TrellixModule,
        symphony_storage: Path,
        session_faker: Faker
        mock_push_data_to_intakes: AsyncMock

    Returns:
        TrellixEdrConnector:
    """
    connector = TrellixEdrConnector(module=module, data_path=symphony_storage)

    # Mock the log function of trigger that requires network access to the api for reporting
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    # Mock the push_events_to_intakes function
    connector.push_data_to_intakes = mock_push_data_to_intakes

    connector.configuration = {
        "intake_key": session_faker.word(),
        "intake_server": session_faker.uri(),
        "ratelimit_per_minute": session_faker.random.randint(1000, 100000),
        "records_per_request": session_faker.random.randint(1, 100),
    }

    return connector


@pytest.mark.asyncio
async def test_trellix_connector_last_event_date(connector: TrellixEdrConnector, session_faker: Faker):
    """
    Test `last_event_date`.

    Args:
        connector: TrellixEdrConnector
        session_faker: Faker
    """
    random_key = session_faker.word()
    with connector.context as cache:
        cache[random_key] = None

    current_date = datetime.now(timezone.utc).replace(microsecond=0)
    one_week_ago = current_date - timedelta(days=7)

    assert connector.last_event_date(random_key) == one_week_ago

    with connector.context as cache:
        cache[random_key] = current_date.isoformat()

    assert connector.last_event_date(random_key) == current_date

    with connector.context as cache:
        cache[random_key] = (one_week_ago - timedelta(days=1)).isoformat()

    assert connector.last_event_date(random_key) == one_week_ago


@pytest.mark.asyncio
async def test_trellix_connector_get_alert_events(
    connector: TrellixEdrConnector,
    session_faker: Faker,
    http_token: HttpToken,
    edr_alert_event_response: tuple[dict[str, Any], TrellixResponse[EdrAlertAttributes]],
):
    """
    Test connector to get alert events.

    Args:
        connector: TrellixEdrConnector
        session_faker: Faker
        http_token: HttpToken
        edr_alert_event_response: tuple[dict[str, Any], TrellixResponse[EdrAlertAttributes]]
    """
    current_date = datetime.now(timezone.utc).replace(microsecond=0)

    with connector.context as cache:
        cache["alerts"] = current_date.isoformat()

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_edr_result = [edr_alert_event_response[0] for _ in range(0, session_faker.pyint(max_value=100))]
        expected_edr_result_dto = [edr_alert_event_response[1].dict() for _ in expected_edr_result]

        mocked_responses.get(
            http_client.edr_alerts_url(current_date, limit=connector.configuration.records_per_request),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_edr_result).decode("utf-8")),
            },
        )

        result, _ = await connector.populate_alerts()

        assert result == [orjson.dumps(event).decode("utf-8") for event in expected_edr_result_dto]


@pytest.mark.asyncio
async def test_trellix_connector_get_detection_events(
    connector: TrellixEdrConnector,
    session_faker: Faker,
    http_token: HttpToken,
    edr_detection_event_response: TrellixResponse[EdrDetectionAttributes],
):
    """
    Test connector to get detection events.

    Args:
        connector: TrellixEdrConnector
        session_faker: Faker
        http_token: HttpToken
        edr_alert_event_response: TrellixResponse[EdrAlertAttributes]
    """
    # Starting from 1 hour ago
    end_date = datetime.now(timezone.utc).replace(microsecond=0)
    start_date = end_date - timedelta(hours=1)
    limit = connector.configuration.records_per_request

    threat_id = str(session_faker.pyint())

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        # Each mock for each request for fresh token. We should have 3 requests
        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict(), repeat=3)

        first_request_expected_detections_result = [
            edr_detection_event_response.dict(exclude_none=True) for _ in range(0, session_faker.pyint(max_value=100))
        ]
        second_request_expected_detections_result = [
            edr_detection_event_response.dict(exclude_none=True) for _ in range(0, session_faker.pyint(max_value=100))
        ]
        third_request_expected_detections_result = []

        mocked_responses.get(
            http_client.edr_threat_detections_url(threat_id, start_date, end_date, limit=limit, offset=0),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(first_request_expected_detections_result).decode("utf-8")),
            },
        )

        mocked_responses.get(
            http_client.edr_threat_detections_url(threat_id, start_date, end_date, limit=limit, offset=limit),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(second_request_expected_detections_result).decode("utf-8")),
            },
        )

        mocked_responses.get(
            http_client.edr_threat_detections_url(threat_id, start_date, end_date, limit=limit, offset=limit * 2),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(third_request_expected_detections_result).decode("utf-8")),
            },
        )

        result = await connector.get_threat_detections(threat_id, start_date, end_date)

        total_expected_detections_result = [
            {**event, "threatId": threat_id}
            for event in first_request_expected_detections_result
            + second_request_expected_detections_result
            + third_request_expected_detections_result
        ]

        assert result == [orjson.dumps(event).decode("utf-8") for event in total_expected_detections_result]


@pytest.mark.asyncio
async def test_trellix_connector_get_affectedhosts_events(
    connector: TrellixEdrConnector,
    session_faker: Faker,
    http_token: HttpToken,
    edr_affectedhost_event_response: TrellixResponse[EdrAffectedhostAttributes],
):
    """
    Test connector to get affected host events.

    Args:
        connector: TrellixEdrConnector
        session_faker: Faker
        http_token: HttpToken
        edr_affectedhost_event_response: TrellixResponse[EdrAffectedhostAttributes]
    """
    # Starting from 1 hour ago
    end_date = datetime.now(timezone.utc).replace(microsecond=0)
    start_date = end_date - timedelta(hours=1)
    limit = connector.configuration.records_per_request

    threat_id = str(session_faker.pyint())

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        # Each mock for each request for fresh token. We should have 3 requests
        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict(), repeat=3)

        first_request_expected_detections_result = [
            edr_affectedhost_event_response.dict(exclude_none=True)
            for _ in range(0, session_faker.pyint(max_value=100))
        ]
        second_request_expected_detections_result = [
            edr_affectedhost_event_response.dict(exclude_none=True)
            for _ in range(0, session_faker.pyint(max_value=100))
        ]
        third_request_expected_detections_result = []

        mocked_responses.get(
            http_client.edr_threat_affectedhosts_url(threat_id, start_date, end_date, limit=limit, offset=0),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(first_request_expected_detections_result).decode("utf-8")),
            },
        )

        mocked_responses.get(
            http_client.edr_threat_affectedhosts_url(threat_id, start_date, end_date, limit=limit, offset=limit),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(second_request_expected_detections_result).decode("utf-8")),
            },
        )

        mocked_responses.get(
            http_client.edr_threat_affectedhosts_url(threat_id, start_date, end_date, limit=limit, offset=limit * 2),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(third_request_expected_detections_result).decode("utf-8")),
            },
        )

        result = await connector.get_threat_affectedhosts(threat_id, start_date, end_date)

        total_expected_detections_result = [
            {**event, "threatId": threat_id}
            for event in first_request_expected_detections_result
            + second_request_expected_detections_result
            + third_request_expected_detections_result
        ]

        assert result == [orjson.dumps(event).decode("utf-8") for event in total_expected_detections_result]


@pytest.mark.asyncio
async def test_trellix_connector_get_threats_events(
    connector: TrellixEdrConnector,
    session_faker: Faker,
    http_token: HttpToken,
    edr_threat_event_response: TrellixResponse[EdrThreatAttributes],
    edr_detection_event_response: TrellixResponse[EdrDetectionAttributes],
    edr_affectedhost_event_response: TrellixResponse[EdrAffectedhostAttributes],
):
    """
    Test connector to get threats host events.

    Args:
        connector: TrellixEdrConnector
        session_faker: Faker
        http_token: HttpToken
        edr_threat_event_response: TrellixResponse[EdrThreatAttributes]
        edr_detection_event_response: TrellixResponse[EdrDetectionAttributes]
        edr_affectedhost_event_response: TrellixResponse[EdrAffectedhostAttributes]
    """
    # Starting from 1 hour ago
    end_date = datetime.now(timezone.utc).replace(microsecond=0)
    start_date = end_date - timedelta(hours=1)

    with connector.context as cache:
        cache["threats"] = start_date.isoformat()

    limit = connector.configuration.records_per_request

    threat_id_1 = str(session_faker.pyint())
    threat_id_2 = str(session_faker.pyint())

    threat_response_1 = edr_threat_event_response.copy()
    threat_response_1.attributes.lastDetected = (end_date - timedelta(minutes=1)).isoformat()
    threat_response_1.id = threat_id_1

    threat_response_2 = edr_threat_event_response.copy()
    threat_response_2.id = threat_id_2

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        # Mocks #1
        # We mock request to get token
        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict(), repeat=100)

        # Mocks #2
        # We mock request to get threats. Let`s say we should send 2 requests. First request
        # will return first threat, second request should return second threat
        first_threat_request_result = [threat_response_1.dict(exclude_none=True)]
        second_threat_request_result = [threat_response_2.dict(exclude_none=True)]

        mocked_responses.get(
            http_client.edr_threats_url(start_date, end_date, limit=limit, offset=0),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(first_threat_request_result).decode("utf-8")),
            },
        )

        mocked_responses.get(
            http_client.edr_threats_url(start_date, end_date, limit=limit, offset=limit),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(second_threat_request_result).decode("utf-8")),
            },
        )

        mocked_responses.get(
            http_client.edr_threats_url(start_date, end_date, limit=limit, offset=limit * 2),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps([]).decode("utf-8")),
            },
        )

        # Mocks #3
        # We mock request to get detections. Let`s say we should send 3 requests for each threat
        # First request will return first max 100 detections, second request should return second 100 detections
        # and third request should return empty list
        first_request_expected_detections_result = [
            edr_detection_event_response.dict(exclude_none=True) for _ in range(0, 1)
        ]
        second_request_expected_detections_result = [
            edr_detection_event_response.dict(exclude_none=True) for _ in range(0, 1)
        ]
        total_detections_expected_result = []
        for threat_id in [threat_id_1, threat_id_2]:
            mocked_responses.get(
                http_client.edr_threat_detections_url(threat_id, start_date, end_date, limit=limit, offset=0),
                status=200,
                payload={
                    "data": orjson.loads(orjson.dumps(first_request_expected_detections_result).decode("utf-8")),
                },
            )

            mocked_responses.get(
                http_client.edr_threat_detections_url(threat_id, start_date, end_date, limit=limit, offset=limit),
                status=200,
                payload={
                    "data": orjson.loads(orjson.dumps(second_request_expected_detections_result).decode("utf-8")),
                },
            )

            mocked_responses.get(
                http_client.edr_threat_detections_url(threat_id, start_date, end_date, limit=limit, offset=limit * 2),
                status=200,
                payload={
                    "data": orjson.loads(orjson.dumps([]).decode("utf-8")),
                },
            )

            total_detections_expected_result.extend(
                [
                    {**event, "threatId": threat_id}
                    for event in first_request_expected_detections_result + second_request_expected_detections_result
                ]
            )

        # Mocks #4
        # We mock request to get affected hosts. Let`s say we should send 3 requests for each threat
        # First request will return first max 100 affected hosts, second request should return second 100 affected hosts
        # and third request should return empty list
        first_request_expected_affectedhosts_result = [
            edr_affectedhost_event_response.dict(exclude_none=True) for _ in range(0, 1)
        ]
        second_request_expected_affectedhosts_result = [
            edr_affectedhost_event_response.dict(exclude_none=True) for _ in range(0, 1)
        ]

        total_affectedhosts_expected_result = []
        for threat_id in [threat_id_1, threat_id_2]:
            mocked_responses.get(
                http_client.edr_threat_affectedhosts_url(threat_id, start_date, end_date, limit=limit, offset=0),
                status=200,
                payload={
                    "data": orjson.loads(orjson.dumps(first_request_expected_affectedhosts_result).decode("utf-8")),
                },
            )

            mocked_responses.get(
                http_client.edr_threat_affectedhosts_url(threat_id, start_date, end_date, limit=limit, offset=limit),
                status=200,
                payload={
                    "data": orjson.loads(orjson.dumps(second_request_expected_affectedhosts_result).decode("utf-8")),
                },
            )

            mocked_responses.get(
                http_client.edr_threat_affectedhosts_url(
                    threat_id, start_date, end_date, limit=limit, offset=limit * 2
                ),
                status=200,
                payload={
                    "data": orjson.loads(orjson.dumps([]).decode("utf-8")),
                },
            )

            total_affectedhosts_expected_result.extend(
                [
                    {**event, "threatId": threat_id}
                    for event in first_request_expected_affectedhosts_result
                    + second_request_expected_affectedhosts_result
                ]
            )

        result, result_end_date = await connector.populate_threats(end_date=end_date)

        assert result_end_date == max(
            [isoparse(threat.attributes.lastDetected) for threat in [threat_response_1, threat_response_2]]
        )

        assert sorted(result) == sorted(
            [
                orjson.dumps(event).decode("utf-8")
                for event in [threat_response_1.dict(exclude_none=True), threat_response_2.dict(exclude_none=True)]
                + total_affectedhosts_expected_result
                + total_detections_expected_result
            ]
        )
