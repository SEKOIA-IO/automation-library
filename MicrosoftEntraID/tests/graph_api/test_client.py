from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from graph_api.client import GraphApi


@pytest.mark.asyncio
async def test_client_get_signins(graph_api_client: GraphApi, signins_page_1, signins_page_2) -> None:
    graph_api_client._client.audit_logs.sign_ins.get.return_value = signins_page_1
    graph_api_client._client.audit_logs.sign_ins.with_url.return_value.get.return_value = signins_page_2

    items = [
        x
        async for x in graph_api_client.get_signin_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [i.id for i in items] == ["0", "1", "2"]
    assert items[0].user_principal_name == "u1@example.com"
    assert items[2].ip_address == "2.2.2.2"


@pytest.mark.asyncio
async def test_client_get_signins_empty(graph_api_client: GraphApi) -> None:
    graph_api_client._client.audit_logs.sign_ins.get.return_value = None

    items = [
        x
        async for x in graph_api_client.get_signin_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [] == items


@pytest.mark.asyncio
async def test_client_get_signins_empty_1(graph_api_client: GraphApi, signins_page_1) -> None:
    graph_api_client._client.audit_logs.sign_ins.get.return_value = signins_page_1
    graph_api_client._client.audit_logs.sign_ins.with_url.return_value.get.return_value = None

    items = [
        x
        async for x in graph_api_client.get_signin_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [i.id for i in items] == ["0", "1"]
    assert items[0].user_principal_name == "u1@example.com"


@pytest.mark.asyncio
async def test_client_get_directory_audits(
    graph_api_client: GraphApi, directory_audits_page_1, directory_audits_page_2
) -> None:
    graph_api_client._client.audit_logs.directory_audits.get.return_value = directory_audits_page_1
    graph_api_client._client.audit_logs.directory_audits.with_url.return_value.get.return_value = (
        directory_audits_page_2
    )

    items = [
        x
        async for x in graph_api_client.get_directory_audit_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [i.id for i in items] == ["3", "4", "5"]
    assert items[0].activity_display_name == "Add user"
    assert items[1].initiated_by.user.display_name == "Admin2"


@pytest.mark.asyncio
async def test_client_get_directory_audits_empty(graph_api_client: GraphApi) -> None:
    graph_api_client._client.audit_logs.directory_audits.get.return_value = None

    items = [
        x
        async for x in graph_api_client.get_directory_audit_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [] == items


@pytest.mark.asyncio
async def test_client_get_directory_audits_empty_1(graph_api_client: GraphApi, directory_audits_page_1) -> None:
    graph_api_client._client.audit_logs.directory_audits.get.return_value = directory_audits_page_1
    graph_api_client._client.audit_logs.directory_audits.with_url.return_value.get.return_value = None

    items = [
        x
        async for x in graph_api_client.get_directory_audit_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [i.id for i in items] == ["3"]
    assert items[0].activity_display_name == "Add user"


@pytest.mark.asyncio
async def test_client_close_closes_http_transport_and_credentials(graph_api_client: GraphApi) -> None:
    request_adapter = MagicMock()
    request_adapter.http_client = MagicMock()
    request_adapter.http_client.aclose = AsyncMock()
    credentials_close = AsyncMock()

    graph_api_client._client.request_adapter = request_adapter
    graph_api_client._credentials.close = credentials_close

    await graph_api_client.close()

    request_adapter.http_client.aclose.assert_awaited_once()
    credentials_close.assert_awaited_once()
    assert graph_api_client._client is None
    assert graph_api_client._credentials is None


@pytest.mark.asyncio
async def test_client_close_clears_refs_even_if_transport_close_fails(graph_api_client: GraphApi) -> None:
    request_adapter = MagicMock()
    request_adapter.http_client = MagicMock()
    request_adapter.http_client.aclose = AsyncMock(side_effect=RuntimeError("boom"))
    credentials_close = AsyncMock()

    graph_api_client._client.request_adapter = request_adapter
    graph_api_client._credentials.close = credentials_close

    with pytest.raises(RuntimeError, match="boom"):
        await graph_api_client.close()

    request_adapter.http_client.aclose.assert_awaited_once()
    credentials_close.assert_awaited_once()
    assert graph_api_client._client is None
    assert graph_api_client._credentials is None
