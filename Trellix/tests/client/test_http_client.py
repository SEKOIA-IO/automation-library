"""Tests for http client."""
import orjson
import pytest
from aioresponses import aioresponses

from client.http_client import TrellixHttpClient
from client.schemas.token import Scope


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
async def test_trellix_http_client_get_headers(session_faker, http_token, edr_epo_event_response):
    """
    Test TrellixHttpClient headers generation.

    Args:
        session_faker: Faker
        http_token: HttpToken
        edr_epo_event_response: TrellixEdrResponse[EpoEventAttributes]
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

        expected_result = [edr_epo_event_response.dict() for _ in range(0, session_faker.pyint(max_value=100))]

        mocked_responses.get(
            http_client.epo_events_url(results_start_date, limit=results_limit),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_result).decode("utf-8")),
            },
        )

        result = await http_client.get_epo_events(results_start_date, results_limit)

        assert result == expected_result
