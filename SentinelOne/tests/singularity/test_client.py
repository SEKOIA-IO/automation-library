from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiolimiter import AsyncLimiter
from gql import gql

from sentinelone_module.singularity.client import ListAlertsResult, SingularityClient


@pytest.fixture
def api_token():
    return "test_token"


@pytest.fixture
def hostname():
    return "testhost"


@pytest.fixture
def client(api_token, hostname):
    return SingularityClient(api_token, hostname)


@pytest.mark.asyncio
async def test_init(api_token, hostname):
    client = SingularityClient(api_token, hostname)
    assert client.api_token == api_token
    assert client.hostname == hostname
    assert client._client is None
    assert client._rate_limiter is None


@pytest.mark.asyncio
async def test_close(client):
    internal_client = AsyncMock()
    internal_client.close_async = AsyncMock()

    client._client = internal_client
    client._rate_limiter = AsyncLimiter(max_rate=1, time_period=3)

    await client.close()

    internal_client.close_async.assert_called_once()
    assert client._client is None
    assert client._rate_limiter is None


@pytest.mark.asyncio
@patch("sentinelone_module.singularity.client.AIOHTTPTransport")
@patch("sentinelone_module.singularity.client.Client")
@patch("sentinelone_module.singularity.client.AsyncLimiter")
async def test_session(mock_limiter, mock_client, mock_transport, client):
    mock_client_instance = AsyncMock()
    mock_client.return_value = mock_client_instance

    mock_transport_instance = MagicMock()
    mock_transport.return_value = mock_transport_instance

    mock_limiter_instance = AsyncMock()
    mock_limiter.return_value = mock_limiter_instance

    async with client._session():
        pass

    mock_transport.assert_called_once_with(
        url=f"https://{client.hostname}/web/api/v2.1/unifiedalerts/graphql",
        headers={"Authorization": f"Bearer {client.api_token}"},
    )
    mock_client.assert_called_once_with(transport=mock_transport_instance)
    mock_limiter.assert_called_once_with(max_rate=25, time_period=1)


@pytest.mark.asyncio
@patch("sentinelone_module.singularity.client.SingularityClient.query", new_callable=AsyncMock)
async def test_list_alerts(mock_query, client):
    alert = {
        "id": "1",
        "name": "alert1",
        "description": "description1",
        "detectedAt": "time",
        "attackSurfaces": [],
        "detectionSource": {"product": "product1"},
        "status": "status",
        "assignee": {"fullName": "assignee1"},
        "classification": "classification",
        "confidenceLevel": "high",
        "firstSeenAt": "time",
        "lastSeenAt": "time",
        "process": {
            "cmdLine": "cmd",
            "file": {"path": "path", "sha1": "sha1", "sha256": "sha256", "md5": "md5"},
            "parentName": "parent",
        },
        "result": "result",
        "storylineId": "storyline",
    }

    mock_query.return_value = {
        "alerts": {
            "totalCount": 1,
            "pageInfo": {"endCursor": "cursor", "hasNextPage": True},
            "edges": [{"node": alert}],
        }
    }

    result = await client.list_alerts("product_name")
    assert result == ListAlertsResult(total_count=1, end_cursor="cursor", has_next_page=True, alerts=[alert])

    mock_query.assert_called_once()


@pytest.mark.asyncio
@patch("sentinelone_module.singularity.client.SingularityClient.query", new_callable=AsyncMock)
async def test_alert_details(mock_query, client):
    details = {"some_details": "some_value"}

    mock_query.return_value = {"alert": details}

    result = await client.get_alert_details("alert_id")
    assert result == details

    mock_query.assert_called_once()
