from datetime import datetime, timedelta

import pytest
from aioresponses import aioresponses

from delinea.client.delinea_client import DelineaClient, DelineaError


@pytest.fixture
def client(base_url: str, client_id: str, client_secret: str) -> DelineaClient:
    """
    Delinea client.

    Args:
        base_url: Base URL for Delinea instance.
        client_id: Client ID for Delinea instance.
        client_secret: Client Secret for Delinea instance.

    Returns:
        DelineaClient:
    """
    return DelineaClient(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
    )


@pytest.mark.asyncio
async def test_client_get_auth_token(client: DelineaClient):
    """
    Test get_auth_token method.

    Args:
        client: Delinea client.
    """
    assert client._access_token is None

    with aioresponses() as m:
        m.post(
            f"{client.base_url}/identity/api/oauth2/token/xpmplatform",
            payload={
                "access_token": "test_token",
                "expires_in": 3600,
            },
        )

        token = await client.get_auth_token()
        assert token == "test_token"
        assert client._access_token == "test_token"


@pytest.mark.asyncio
async def test_client_get_auth_token_error(client: DelineaClient):
    """
    Test get_auth_token method with cached token.

    Args:
        client: Delinea client.
    """
    assert client._access_token is None

    with aioresponses() as m:
        m.post(
            f"{client.base_url}/identity/api/oauth2/token/xpmplatform",
            payload={
                "random_value": "test_token",
            },
        )

        with pytest.raises(ValueError):
            await client.get_auth_token()

        assert client._access_token is None


@pytest.mark.asyncio
async def test_client_get_auth_token_error_2(client: DelineaClient):
    """
    Test get_auth_token method with cached token.

    Args:
        client: Delinea client.
    """
    assert client._access_token is None

    with aioresponses() as m:
        m.post(f"{client.base_url}/identity/api/oauth2/token/xpmplatform", body="Internal Server Error", status=500)

        with pytest.raises(DelineaError):
            await client.get_auth_token()

        assert client._access_token is None


@pytest.mark.asyncio
async def test_client_get_audit_events(client: DelineaClient):
    """
    Test get audit.

    Args:
        client: Delinea client.
    """
    assert client._access_token is None

    with aioresponses() as m:
        m.post(
            f"{client.base_url}/identity/api/oauth2/token/xpmplatform",
            payload={
                "access_token": "access_token",
                "expires_in": 0,  # simulate immediate expiry
            },
        )

        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now() - timedelta(hours=1)

        first_response = {
            "auditEvents": [
                {"event_id": 1},
                {"event_id": 2},
            ],
        }

        audit_events_url_1 = client.get_audit_events_url(start_date=start_date, page=1, end_date=end_date)
        m.get(audit_events_url_1, payload=first_response)

        m.post(
            f"{client.base_url}/identity/api/oauth2/token/xpmplatform",
            payload={
                "access_token": "access_token",
                "expires_in": 10,
            },
        )

        second_response = {}
        audit_events_url_2 = client.get_audit_events_url(start_date=start_date, page=2, end_date=end_date)
        m.get(audit_events_url_2, payload=second_response)

        result = []
        async for event in client.get_audit_events(start_date=start_date, end_date=end_date):
            result.append(event)

        assert len(result) == 2
        assert result[0] == {"event_id": 1}
        assert result[1] == {"event_id": 2}

        await client.close()
