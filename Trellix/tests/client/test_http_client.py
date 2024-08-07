"""Tests for http client."""

from typing import Any
from unittest.mock import patch

import orjson
import pytest
from aioresponses import aioresponses
from faker import Faker

from client.http_client import TrellixHttpClient
from client.schemas.attributes.edr_affectedhosts import EdrAffectedhostAttributes
from client.schemas.attributes.edr_alerts import EdrAlertAttributes
from client.schemas.attributes.edr_detections import EdrDetectionAttributes
from client.schemas.attributes.edr_threats import EdrThreatAttributes
from client.schemas.attributes.epo_events import EpoEventAttributes
from client.schemas.token import HttpToken, Scope
from client.schemas.trellix_response import TrellixResponse


@pytest.mark.asyncio
async def test_trellix_http_client_init(session_faker):
    """
    Test TrellixHttpClient.instance.

    Args:
        session_faker: Faker
    """
    auth_url = session_faker.uri()
    base_url = session_faker.uri()
    client_id = session_faker.word()
    client_secret = session_faker.word()
    api_key = session_faker.word()

    http_client = await TrellixHttpClient.instance(client_id, client_secret, api_key, auth_url, base_url)
    http_client_1 = await TrellixHttpClient.instance(client_id, client_secret, api_key, auth_url, base_url)

    async with http_client.session() as session_1:
        async with http_client.session() as session_2:
            async with http_client_1.session() as session_3:
                assert session_1 is session_2
                assert session_1 is session_3

                assert http_client is http_client_1


@pytest.mark.asyncio
async def test_trellix_http_client_get_epo_events(
    session_faker: Faker, http_token: HttpToken, epo_event_response: TrellixResponse[EpoEventAttributes]
):
    """
    Test get epo events.

    Args:
        session_faker: Faker
        http_token: HttpToken
        epo_event_response: TrellixResponse[EpoEventAttributes]
    """
    with aioresponses() as mocked_responses:
        base_url = session_faker.uri()
        base_auth_url = session_faker.uri()
        client_id = session_faker.word()
        client_secret = session_faker.word()
        api_key = session_faker.word()

        results_limit = session_faker.pyint()
        results_start_date = session_faker.date_time()

        http_client = await TrellixHttpClient.instance(
            client_id,
            client_secret,
            api_key,
            base_auth_url,
            base_url,
        )

        token_refresher = await http_client._get_token_refresher(Scope.complete_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_result = [epo_event_response.dict() for _ in range(0, session_faker.pyint(max_value=100))]

        mocked_responses.get(
            http_client.epo_events_url(results_start_date, limit=results_limit),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_result).decode("utf-8")),
            },
        )

        result = await http_client.get_epo_events(results_start_date, results_limit)

        assert result == expected_result


@pytest.mark.asyncio
async def test_trellix_http_client_get_edr_threat_events(
    session_faker: Faker, http_token: HttpToken, edr_threat_event_response: TrellixResponse[EdrThreatAttributes]
):
    """
    Test get edr threat events.

    Args:
        session_faker: Faker
        http_token: HttpToken
        edr_threat_event_response: TrellixResponse[EdrThreatAttributes]
    """
    with aioresponses() as mocked_responses:
        base_url = session_faker.uri()
        base_auth_url = session_faker.uri()
        client_id = session_faker.word()
        client_secret = session_faker.word()
        api_key = session_faker.word()

        results_limit = session_faker.pyint()
        results_offset = session_faker.pyint()
        results_start_date = session_faker.date_time()
        results_end_date = session_faker.date_time()

        http_client = await TrellixHttpClient.instance(
            client_id,
            client_secret,
            api_key,
            base_auth_url,
            base_url,
        )

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_result = [edr_threat_event_response.dict() for _ in range(0, session_faker.pyint(max_value=100))]

        mocked_responses.get(
            http_client.edr_threats_url(
                results_start_date, results_end_date, limit=results_limit, offset=results_offset
            ),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_result).decode("utf-8")),
            },
        )

        result = await http_client.get_edr_threats(results_start_date, results_end_date, results_limit, results_offset)

        assert result == expected_result


@pytest.mark.asyncio
async def test_trellix_http_client_get_edr_detection_events(
    session_faker: Faker, http_token: HttpToken, edr_detection_event_response: TrellixResponse[EdrDetectionAttributes]
):
    """
    Test get edr detection events.

    Args:
        session_faker: Faker
        http_token: HttpToken
        edr_detection_event_response: TrellixResponse[EdrDetectionAttributes]
    """
    with aioresponses() as mocked_responses:
        base_url = session_faker.uri()
        base_auth_url = session_faker.uri()
        client_id = session_faker.word()
        client_secret = session_faker.word()
        api_key = session_faker.word()

        threat_id = str(session_faker.pyint())
        results_limit = session_faker.pyint()
        results_offset = session_faker.pyint()
        results_start_date = session_faker.date_time()
        results_end_date = session_faker.date_time()

        http_client = await TrellixHttpClient.instance(
            client_id,
            client_secret,
            api_key,
            base_auth_url,
            base_url,
        )

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_result = [edr_detection_event_response.dict() for _ in range(0, session_faker.pyint(max_value=100))]

        mocked_responses.get(
            http_client.edr_threat_detections_url(
                threat_id, results_start_date, results_end_date, limit=results_limit, offset=results_offset
            ),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_result).decode("utf-8")),
            },
        )

        result = await http_client.get_edr_threat_detections(
            threat_id, results_start_date, results_end_date, results_limit, results_offset
        )

        assert result == expected_result


@pytest.mark.asyncio
async def test_trellix_http_client_get_edr_affectedhost_events(
    session_faker: Faker,
    http_token: HttpToken,
    edr_affectedhost_event_response: TrellixResponse[EdrAffectedhostAttributes],
):
    """
    Test get edr affectedhost events.

    Args:
        session_faker: Faker
        http_token: HttpToken
        edr_affectedhost_event_response: TrellixResponse[EdrAffectedhostAttributes]
    """
    with aioresponses() as mocked_responses:
        base_url = session_faker.uri()
        base_auth_url = session_faker.uri()
        client_id = session_faker.word()
        client_secret = session_faker.word()
        api_key = session_faker.word()

        threat_id = str(session_faker.pyint())
        results_limit = session_faker.pyint()
        results_offset = session_faker.pyint()
        results_start_date = session_faker.date_time()
        results_end_date = session_faker.date_time()

        http_client = await TrellixHttpClient.instance(
            client_id,
            client_secret,
            api_key,
            base_auth_url,
            base_url,
        )

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_result = [
            edr_affectedhost_event_response.dict() for _ in range(0, session_faker.pyint(max_value=100))
        ]

        mocked_responses.get(
            http_client.edr_threat_affectedhosts_url(
                threat_id, results_start_date, results_end_date, limit=results_limit, offset=results_offset
            ),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_result).decode("utf-8")),
            },
        )

        result = await http_client.get_edr_threat_affectedhosts(
            threat_id, results_start_date, results_end_date, results_limit, results_offset
        )

        assert result == expected_result


@pytest.mark.asyncio
async def test_trellix_http_client_get_edr_alert_events(
    session_faker: Faker,
    http_token: HttpToken,
    edr_alert_event_response: tuple[dict[str, Any], TrellixResponse[EdrAlertAttributes]],
):
    """
    Test get edr alert events.

    Args:
        session_faker: Faker
        http_token: HttpToken
        edr_alert_event_response: tuple[dict[str, Any], TrellixResponse[EdrAlertAttributes]]
    """
    with aioresponses() as mocked_responses:
        base_url = session_faker.uri()
        base_auth_url = session_faker.uri()
        client_id = session_faker.word()
        client_secret = session_faker.word()
        api_key = session_faker.word()

        results_limit = session_faker.pyint()
        results_start_date = session_faker.date_time()

        http_client = await TrellixHttpClient.instance(
            client_id,
            client_secret,
            api_key,
            base_auth_url,
            base_url,
        )

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_result = [edr_alert_event_response[0] for _ in range(0, session_faker.pyint(max_value=100))]
        expected_result_dto = [edr_alert_event_response[1] for _ in expected_result]

        mocked_responses.get(
            http_client.edr_alerts_url(results_start_date, limit=results_limit),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_result).decode("utf-8")),
            },
        )

        result = await http_client.get_edr_alerts(results_start_date, results_limit)

        assert result == expected_result_dto


@pytest.mark.asyncio
async def test_trellix_http_client_retry(
    session_faker: Faker,
    http_token: HttpToken,
    edr_alert_event_response: tuple[dict[str, Any], TrellixResponse[EdrAlertAttributes]],
):
    """
    Test get edr alert events.

    Args:
        session_faker: Faker
        http_token: HttpToken
        edr_alert_event_response: tuple[dict[str, Any], TrellixResponse[EdrAlertAttributes]]
    """
    with aioresponses() as mocked_responses:
        base_url = session_faker.uri()
        base_auth_url = session_faker.uri()
        client_id = session_faker.word()
        client_secret = session_faker.word()
        api_key = session_faker.word()

        results_limit = session_faker.pyint()
        results_start_date = session_faker.date_time()

        http_client = await TrellixHttpClient.instance(
            client_id,
            client_secret,
            api_key,
            base_auth_url,
            base_url,
        )

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_result = [edr_alert_event_response[0] for _ in range(0, session_faker.pyint(max_value=100))]
        expected_result_dto = [edr_alert_event_response[1] for _ in expected_result]

        url = http_client.edr_alerts_url(results_start_date, limit=results_limit)
        mocked_responses.get(
            url,
            status=500,
        )
        mocked_responses.get(
            http_client.edr_alerts_url(results_start_date, limit=results_limit),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_result).decode("utf-8")),
            },
        )
        result = await http_client.get_edr_alerts(results_start_date, results_limit)

        assert result == expected_result_dto


@pytest.mark.asyncio
async def test_trellix_http_client_api_limit_exhausted(
    session_faker: Faker,
    http_token: HttpToken,
    edr_alert_event_response: tuple[dict[str, Any], TrellixResponse[EdrAlertAttributes]],
):
    """
    Test get edr alert events.

    Args:
        session_faker: Faker
        http_token: HttpToken
        edr_alert_event_response: tuple[dict[str, Any], TrellixResponse[EdrAlertAttributes]]
    """
    with aioresponses() as mocked_responses:
        base_url = session_faker.uri()
        base_auth_url = session_faker.uri()
        client_id = session_faker.word()
        client_secret = session_faker.word()
        api_key = session_faker.word()

        results_limit = session_faker.pyint()
        results_start_date = session_faker.date_time()

        http_client = await TrellixHttpClient.instance(
            client_id,
            client_secret,
            api_key,
            base_auth_url,
            base_url,
        )

        token_refresher = await http_client._get_token_refresher(Scope.threats_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_result = [edr_alert_event_response[0] for _ in range(0, session_faker.pyint(max_value=100))]
        expected_result_dto = [edr_alert_event_response[1] for _ in expected_result]

        url = http_client.edr_alerts_url(results_start_date, limit=results_limit)
        mocked_responses.get(url, status=429, headers={"Retry-After": "300"})
        mocked_responses.get(
            http_client.edr_alerts_url(results_start_date, limit=results_limit),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_result).decode("utf-8")),
            },
        )
        with patch("asyncio.sleep") as mock_sleep:
            result = await http_client.get_edr_alerts(results_start_date, results_limit)

            assert result == expected_result_dto
            mock_sleep.assert_called_once_with(300)
