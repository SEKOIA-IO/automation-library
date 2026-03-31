import json
from datetime import datetime, timezone

import pytest
from msgraph.generated.models.directory_audit import DirectoryAudit

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


def test_encode_log_parses_modified_properties(
    directory_audit_with_modified_properties: DirectoryAudit,
) -> None:
    result = json.loads(GraphApi.encode_log(directory_audit_with_modified_properties))

    modified_props = result["targetResources"][0]["modifiedProperties"]

    # ConditionalAccessPolicy: oldValue/newValue should be parsed into dicts
    ca_prop = modified_props[0]
    assert ca_prop["displayName"] == "ConditionalAccessPolicy"
    assert isinstance(ca_prop["oldValue"], dict)
    assert ca_prop["oldValue"]["State"] == "Disabled"
    assert isinstance(ca_prop["newValue"], dict)
    assert ca_prop["newValue"]["State"] == "Enabled"

    # DisplayName: simple quoted strings should be parsed into plain strings
    name_prop = modified_props[1]
    assert name_prop["oldValue"] == "Old Policy Name"
    assert name_prop["newValue"] == "New Policy Name"


def test_encode_log_leaves_non_json_values_as_strings(
    directory_audits_page_1: object,
) -> None:
    """Events without modifiedProperties should serialize without errors."""
    audit = directory_audits_page_1.value[0]  # type: ignore[attr-defined]
    result = json.loads(GraphApi.encode_log(audit))

    assert result["activityDisplayName"] == "Add user"
