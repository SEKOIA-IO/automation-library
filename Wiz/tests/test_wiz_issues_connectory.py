import pytest
from aioresponses import aioresponses

from wiz import WizConnectorConfig, WizModule
from wiz.wiz_issues_connector import WizIssuesConnector


@pytest.fixture
def wiz_issues_connector(
    module: WizModule,
    mock_push_data_to_intakes,
    wiz_gql_client,
) -> WizIssuesConnector:
    connector = WizIssuesConnector()
    connector.configuration = WizConnectorConfig(
        intake_key="test_key",
    )

    connector._wiz_gql_client = wiz_gql_client

    connector.module = module

    connector.push_data_to_intakes = mock_push_data_to_intakes

    return connector


@pytest.mark.asyncio
async def test_wiz_issues_connector(
    auth_url,
    tenant_url,
    wiz_issues_connector,
    alerts_response_with_next_page,
    alerts_response,
    http_token,
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": alerts_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": alerts_response})

        result = await wiz_issues_connector.single_run()

        assert result == len(alerts_response["issuesV2"]["nodes"]) + len(
            alerts_response_with_next_page["issuesV2"]["nodes"]
        )

        await wiz_issues_connector._wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_issues_connector_with_duplicates(
    auth_url,
    tenant_url,
    wiz_issues_connector,
    alerts_response_with_next_page,
    alerts_response,
    http_token,
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": alerts_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": alerts_response_with_next_page})
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": alerts_response})

        result = await wiz_issues_connector.single_run()

        assert result == len(alerts_response["issuesV2"]["nodes"]) + len(
            alerts_response_with_next_page["issuesV2"]["nodes"]
        )

        await wiz_issues_connector._wiz_gql_client.close()
