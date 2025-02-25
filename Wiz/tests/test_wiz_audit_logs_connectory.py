import pytest
from aioresponses import aioresponses

from wiz import WizConnectorConfig, WizModule
from wiz.wiz_audit_logs_connector import WizAuditLogsConnector


@pytest.fixture
def wiz_audit_logs_connector(
    module: WizModule,
    mock_push_data_to_intakes,
    wiz_gql_client,
) -> WizAuditLogsConnector:
    connector = WizAuditLogsConnector()
    connector.configuration = WizConnectorConfig(
        intake_key="test_key",
    )

    connector._wiz_gql_client = wiz_gql_client

    connector.module = module

    connector.push_data_to_intakes = mock_push_data_to_intakes

    return connector


@pytest.mark.asyncio
async def test_wiz_cloud_configuration_findings_connector(
    auth_url,
    tenant_url,
    wiz_audit_logs_connector,
    audit_logs_response_with_next_page,
    audit_logs_response,
    http_token,
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": audit_logs_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": audit_logs_response})

        result = await wiz_audit_logs_connector.single_run()

        assert result == len(audit_logs_response_with_next_page["auditLogEntries"]["nodes"]) + len(
            audit_logs_response["auditLogEntries"]["nodes"]
        )

        await wiz_audit_logs_connector._wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_cloud_configuration_findings_connector_with_duplicates(
    auth_url,
    tenant_url,
    wiz_audit_logs_connector,
    audit_logs_response_with_next_page,
    audit_logs_response,
    http_token,
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": audit_logs_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": audit_logs_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": audit_logs_response})

        result = await wiz_audit_logs_connector.single_run()

        assert result == len(audit_logs_response_with_next_page["auditLogEntries"]["nodes"]) + len(
            audit_logs_response["auditLogEntries"]["nodes"]
        )

        await wiz_audit_logs_connector._wiz_gql_client.close()
