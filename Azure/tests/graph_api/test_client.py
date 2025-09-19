from datetime import datetime
from urllib.parse import urlencode

import pytest
from aioresponses import aioresponses

from graph_api.client import GraphAPIError, GraphAuditClient


@pytest.fixture
def client(audit_credentials):
    return GraphAuditClient(**audit_credentials)


@pytest.mark.asyncio
async def test_client_ensure_token_1(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    assert client._token is None

    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        await client._ensure_token()

        assert client._token == "test_access_token"


@pytest.mark.asyncio
async def test_client_ensure_token_error_1(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    assert client._token is None

    with pytest.raises(GraphAPIError):
        with aioresponses() as mocked_responses:
            mocked_responses.post(
                graph_api_token_url,
                status=400,
                payload={
                    "access_token": "test_access_token",
                    "expires_in": 3600,
                },
            )

            await client._ensure_token()


@pytest.mark.asyncio
async def test_client_ensure_token_error_2(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    assert client._token is None

    with pytest.raises(GraphAPIError):
        with aioresponses() as mocked_responses:
            mocked_responses.post(
                graph_api_token_url,
                status=200,
                payload={
                    "random_result": "test_access_token",
                },
            )

            await client._ensure_token()


@pytest.mark.asyncio
async def test_client_get_directory_audit_logs_1(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/directoryAudits?$top=1000",
            status=200,
            payload={
                "value": [
                    {"id": "log1"},
                    {"id": "log2"},
                ]
            },
        )

        logs = []
        async for item in client.list_directory_audits():
            logs.append(item)

        assert len(logs) == 2
        assert logs[0]["id"] == "log1"
        assert logs[1]["id"] == "log2"

        await client.close()


@pytest.mark.asyncio
async def test_client_get_directory_audit_logs_2(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        query = {
            "$top": 10,
            "$filter": "activityDateTime ge 2023-01-01T00:00:00Z and activityDateTime le 2023-01-02T00:00:00Z",
        }

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/directoryAudits?{urlencode(query)}",
            status=200,
            payload={
                "@odata.nextLink": "http://test.test",
                "value": [
                    {"id": "log1"},
                    {"id": "log2"},
                ],
            },
        )

        mocked_responses.get(
            "http://test.test",
            status=200,
            payload={
                "value": [
                    {"id": "log3"},
                ]
            },
        )

        logs = []
        async for item in client.list_directory_audits(
            start=datetime.strptime("2023-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"),
            end=datetime.strptime("2023-01-02T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"),
            top=10,
        ):
            logs.append(item)

        assert len(logs) == 3
        assert logs[0]["id"] == "log1"
        assert logs[1]["id"] == "log2"
        assert logs[2]["id"] == "log3"

        await client.close()


@pytest.mark.asyncio
async def test_client_get_signin_audit_logs_1(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$top=1000",
            status=200,
            payload={
                "value": [
                    {"id": "log1"},
                    {"id": "log2"},
                ]
            },
        )

        logs = []
        async for item in client.list_signins():
            logs.append(item)

        assert len(logs) == 2
        assert logs[0]["id"] == "log1"
        assert logs[1]["id"] == "log2"

        await client.close()


@pytest.mark.asyncio
async def test_client_get_signin_audit_logs_2(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        query = {
            "$filter": "createdDateTime ge 2023-01-01T00:00:00Z and createdDateTime le 2023-01-02T00:00:00Z",
            "$top": 10,
            "$select": "id,activityDateTime",
            "$orderby": "activityDateTime desc",
        }

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/signIns?{urlencode(query)}",
            status=200,
            payload={
                "@odata.nextLink": "http://test.test",
                "value": [
                    {"id": "log1"},
                    {"id": "log2"},
                ],
            },
        )

        mocked_responses.get(
            "http://test.test",
            status=200,
            payload={
                "value": [
                    {"id": "log3"},
                ]
            },
        )

        logs = []
        async for item in client.list_signins(
            start=datetime.strptime("2023-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"),
            end=datetime.strptime("2023-01-02T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ"),
            top=10,
            select=["id", "activityDateTime"],
            orderby="activityDateTime desc",
        ):
            logs.append(item)

        assert len(logs) == 3
        assert logs[0]["id"] == "log1"
        assert logs[1]["id"] == "log2"
        assert logs[2]["id"] == "log3"

        await client.close()


@pytest.mark.asyncio
async def test_client_get_signin_audit_logs_error_1(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$top=1000",
            status=400,
            payload={
                "error": {
                    "code": "BadRequest",
                    "message": "Invalid request",
                }
            },
        )

        with pytest.raises(GraphAPIError) as exc_info:
            async for _ in client.list_signins():
                pass


@pytest.mark.asyncio
async def test_client_get_signin_audit_logs_401(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$top=1000",
            status=401,
            payload={
                "error": {
                    "code": "BadRequest",
                    "message": "Invalid request",
                }
            },
        )

        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "other_access_token",
                "expires_in": 3600,
            },
        )

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$top=1000",
            status=200,
            payload={
                "value": [
                    {
                        "code": "BadRequest",
                        "message": "Invalid request",
                    }
                ]
            },
        )

        async for _ in client.list_signins():
            pass


@pytest.mark.asyncio
async def test_client_get_signin_audit_logs_error_500(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$top=1000",
            status=500,
            payload={
                "error": {
                    "code": "Server Error",
                    "message": "Server Error",
                }
            },
        )

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$top=1000",
            status=200,
            payload={
                "value": [
                    {
                        "code": "BadRequest",
                        "message": "Invalid request",
                    }
                ]
            },
        )

        async for _ in client.list_signins():
            pass


@pytest.mark.asyncio
async def test_client_get_signin_audit_logs_error_500(
    client: GraphAuditClient, audit_credentials: dict[str, str], graph_api_token_url: str
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$top=1000",
            status=429,
            payload={
                "error": {
                    "code": "Retry after some time",
                    "message": "Retry after some time",
                }
            },
        )

        mocked_responses.get(
            f"https://graph.microsoft.com/v1.0/auditLogs/signIns?$top=1000",
            status=200,
            payload={
                "value": [
                    {
                        "code": "BadRequest",
                        "message": "Invalid request",
                    }
                ]
            },
        )

        async for _ in client.list_signins():
            pass
