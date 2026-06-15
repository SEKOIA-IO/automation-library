from datetime import datetime, timezone

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
async def test_client_get_signins_uses_beta_endpoint_when_enabled(
    graph_api_client: GraphApi, signins_page_1, signins_page_2
) -> None:
    graph_api_client._use_beta_signin_api = True
    graph_api_client._client.audit_logs.sign_ins.with_url.return_value.get.side_effect = [
        signins_page_1,
        signins_page_2,
    ]

    items = [
        x
        async for x in graph_api_client.get_signin_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [i.id for i in items] == ["0", "1", "2"]
    graph_api_client._client.audit_logs.sign_ins.get.assert_not_called()
    graph_api_client._client.audit_logs.sign_ins.with_url.assert_any_call(
        "https://graph.microsoft.com/beta/auditLogs/signIns"
        "?$filter=createdDateTime+ge+2025-09-01T00%3A00%3A00Z"
        "&$orderby=createdDateTime+asc"
    )


@pytest.mark.asyncio
async def test_client_get_signins_uses_beta_endpoint_with_end_date(graph_api_client: GraphApi, signins_page_2) -> None:
    graph_api_client._use_beta_signin_api = True
    graph_api_client._client.audit_logs.sign_ins.with_url.return_value.get.return_value = signins_page_2

    items = [
        x
        async for x in graph_api_client.get_signin_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc),
            datetime.fromisoformat("2025-09-01T12:30:45").replace(tzinfo=timezone.utc),
        )
    ]

    assert [i.id for i in items] == ["2"]
    graph_api_client._client.audit_logs.sign_ins.with_url.assert_any_call(
        "https://graph.microsoft.com/beta/auditLogs/signIns"
        "?$filter=createdDateTime+ge+2025-09-01T00%3A00%3A00Z+and+createdDateTime+le+2025-09-01T12%3A30%3A45Z"
        "&$orderby=createdDateTime+asc"
    )


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
