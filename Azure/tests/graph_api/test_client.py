from datetime import datetime, timezone

import pytest

from graph_api.client import GraphApi


@pytest.mark.asyncio
async def test_client_get_signins(client: GraphApi, signins_page_1, signins_page_2) -> None:
    client._client.audit_logs.sign_ins.get.return_value = signins_page_1
    client._client.audit_logs.sign_ins.with_url.return_value.get.return_value = signins_page_2

    items = [
        x
        async for x in client.get_signin_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [i.id for i in items] == ["0", "1", "2"]
    assert items[0].user_principal_name == "u1@example.com"
    assert items[2].ip_address == "2.2.2.2"


@pytest.mark.asyncio
async def test_client_get_signins_empty(client: GraphApi) -> None:
    client._client.audit_logs.sign_ins.get.return_value = None

    items = [
        x
        async for x in client.get_signin_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [] == items


@pytest.mark.asyncio
async def test_client_get_signins_empty_1(client: GraphApi, signins_page_1) -> None:
    client._client.audit_logs.sign_ins.get.return_value = signins_page_1
    client._client.audit_logs.sign_ins.with_url.return_value.get.return_value = None

    items = [
        x
        async for x in client.get_signin_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [i.id for i in items] == ["0", "1"]
    assert items[0].user_principal_name == "u1@example.com"


@pytest.mark.asyncio
async def test_client_get_directory_audits(client: GraphApi, directory_audits_page_1, directory_audits_page_2) -> None:
    client._client.audit_logs.directory_audits.get.return_value = directory_audits_page_1
    client._client.audit_logs.directory_audits.with_url.return_value.get.return_value = directory_audits_page_2

    items = [
        x
        async for x in client.get_directory_audit_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [i.id for i in items] == ["3", "4", "5"]
    assert items[0].activity_display_name == "Add user"
    assert items[1].initiated_by.user.display_name == "Admin2"


@pytest.mark.asyncio
async def test_client_get_directory_audits_empty(client: GraphApi) -> None:
    client._client.audit_logs.directory_audits.get.return_value = None

    items = [
        x
        async for x in client.get_directory_audit_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [] == items


@pytest.mark.asyncio
async def test_client_get_directory_audits_empty_1(client: GraphApi, directory_audits_page_1) -> None:
    client._client.audit_logs.directory_audits.get.return_value = directory_audits_page_1
    client._client.audit_logs.directory_audits.with_url.return_value.get.return_value = None

    items = [
        x
        async for x in client.get_directory_audit_logs(
            datetime.fromisoformat("2025-09-01T00:00:00").replace(tzinfo=timezone.utc)
        )
    ]

    assert [i.id for i in items] == ["3"]
    assert items[0].activity_display_name == "Add user"
