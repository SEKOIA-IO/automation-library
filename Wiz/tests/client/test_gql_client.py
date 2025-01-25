import datetime

import pytest
from aioresponses import aioresponses

from wiz.client.gql_client import GetAlertsResult


@pytest.mark.asyncio
async def test_wiz_gql_client_request(http_token, session_faker, wiz_gql_client, auth_url, tenant_url):
    """
    Test WizGqlClient.request method

    Args:
        http_token: WizToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
    """
    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": {"test": "test"}})

        result = await wiz_gql_client.request("query { test }")

        assert result == {"test": "test"}

        await wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_gql_client_get_alerts(
    http_token,
    session_faker,
    wiz_gql_client,
    auth_url,
    tenant_url,
    alerts_response,
    alerts_response_with_next_page,
):
    """
    Test WizGqlClient.get_alerts method

    Args:
        http_token: WizHttpToken
        session_faker: Faker
        wiz_gql_client: WizGqlClient
        auth_url: str
        tenant_url: str
        alerts_response: dict[str, Any]
        alerts_response_with_next_page: dict[str, Any]
    """
    date = datetime.datetime.now()

    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": alerts_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": alerts_response})

        result = await wiz_gql_client.get_alerts(date)
        expected_result = GetAlertsResult.from_response(alerts_response_with_next_page)
        assert result == expected_result

        result = await wiz_gql_client.get_alerts(date, expected_result.end_cursor)
        expected_result = GetAlertsResult.from_response(alerts_response)
        assert result == expected_result

        await wiz_gql_client.close()
