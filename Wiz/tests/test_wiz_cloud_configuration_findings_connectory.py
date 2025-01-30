import pytest
from aioresponses import aioresponses

from wiz import WizConnectorConfig, WizModule
from wiz.wiz_cloud_configuration_findings import WizCloudConfigurationFindingsConnector
from wiz.wiz_issues_connector import WizIssuesConnector


@pytest.fixture
def wiz_findings_connector(
    module: WizModule,
    mock_push_data_to_intakes,
    wiz_gql_client,
) -> WizCloudConfigurationFindingsConnector:
    connector = WizCloudConfigurationFindingsConnector()
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
    wiz_findings_connector,
    findings_response_with_next_page,
    findings_response,
    http_token,
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": findings_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": findings_response})

        result = await wiz_findings_connector.single_run()

        assert result == len(findings_response_with_next_page["configurationFindings"]["nodes"]) + len(
            findings_response["configurationFindings"]["nodes"]
        )
