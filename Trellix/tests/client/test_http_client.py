"""Tests for http client."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import orjson
import pytest
from aiolimiter import AsyncLimiter
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

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump())

        expected_result = [epo_event_response.model_dump() for _ in range(0, session_faker.pyint(max_value=100))]

        mocked_responses.get(
            http_client.epo_events_url(results_start_date, limit=results_limit),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_result).decode("utf-8")),
            },
        )

        result = await http_client.get_epo_events(results_start_date, results_limit)

        assert [event.model_dump() for event in result] == expected_result


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

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump())

        expected_result = [
            edr_threat_event_response.model_dump() for _ in range(0, session_faker.pyint(max_value=100))
        ]

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

        assert [event.model_dump() for event in result] == expected_result


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

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump())

        expected_result = [
            edr_detection_event_response.model_dump() for _ in range(0, session_faker.pyint(max_value=100))
        ]

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

        assert [event.model_dump() for event in result] == expected_result


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

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump())

        expected_result = [
            edr_affectedhost_event_response.model_dump() for _ in range(0, session_faker.pyint(max_value=100))
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

        assert [event.model_dump() for event in result] == expected_result


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

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump())

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

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump())

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

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump())

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


@pytest.mark.asyncio
async def test_trellix_http_client_logs_daily_rate_limit_once(session_faker: Faker):
    """Reaching the daily budget is logged once, and so is the recovery, not every throttled request."""
    TrellixHttpClient.set_rate_limiter(AsyncLimiter(1000, time_period=60))
    # 2 requests per 0.1 s: the third request of the burst waits for ~0.05 s
    TrellixHttpClient.set_rate_limiter_per_day(AsyncLimiter(2, time_period=0.1))
    TrellixHttpClient._daily_rate_limit_reached = False

    try:
        with patch("client.http_client.logger") as mocked_logger:
            for _ in range(4):
                async with TrellixHttpClient.session():
                    pass

            assert mocked_logger.warning.call_count == 1
            assert "Daily request limit of 2 reached" in mocked_logger.warning.call_args.args[0].format(
                **mocked_logger.warning.call_args.kwargs
            )

            await asyncio.sleep(0.2)
            async with TrellixHttpClient.session():
                pass

            assert mocked_logger.info.call_count == 1
            assert mocked_logger.warning.call_count == 1
    finally:
        TrellixHttpClient._rate_limiter = None
        TrellixHttpClient._rate_limiter_per_day = None
        TrellixHttpClient._daily_rate_limit_reached = False


def test_trellix_http_client_resolve_next_link():
    """`links.next` is resolved against the request URL and must stay on the origin of `base_url`."""
    http_client = TrellixHttpClient("id", "secret", "key", "https://auth.example.com", "https://api.example.com/v1")
    request_url = http_client.epo_events_url(datetime(2026, 10, 26, tzinfo=UTC), limit=100)

    def resolve(next_link: Any) -> str | None:
        url = http_client._resolve_next_link({"data": [], "links": {"next": next_link}}, request_url)
        return None if url is None else str(url)

    assert resolve("?page%5Boffset%5D=100") == "https://api.example.com/v1/epo/v2/events?page%5Boffset%5D=100"
    assert (
        resolve("/epo/v2/events?page%5Boffset%5D=100") == "https://api.example.com/epo/v2/events?page%5Boffset%5D=100"
    )
    assert (
        resolve("https://api.example.com/v1/epo/v2/events?page%5Boffset%5D=100")
        == "https://api.example.com/v1/epo/v2/events?page%5Boffset%5D=100"
    )
    assert resolve("https://evil.example.com/epo/v2/events") is None
    assert resolve(None) is None
    assert resolve("") is None
    assert http_client._resolve_next_link({"data": []}, request_url) is None
