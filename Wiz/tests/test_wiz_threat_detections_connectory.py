import pytest
from aioresponses import aioresponses

from wiz import WizConnectorConfig, WizModule
from wiz.wiz_threat_detections_connector import WizThreatDetectionsConnector


@pytest.fixture
def wiz_threat_detections(
    module: WizModule,
    mock_push_data_to_intakes,
    wiz_gql_client,
) -> WizThreatDetectionsConnector:
    connector = WizThreatDetectionsConnector()
    connector.configuration = WizConnectorConfig(
        intake_key="test_key",
    )

    connector._wiz_gql_client = wiz_gql_client

    connector.module = module

    connector.push_data_to_intakes = mock_push_data_to_intakes

    return connector


@pytest.mark.asyncio
async def test_wiz_threat_detections(
    auth_url,
    tenant_url,
    wiz_threat_detections,
    threat_detections_response_with_next_page,
    threat_detections_response,
    http_token,
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(
            tenant_url + "graphql", status=200, payload={"data": threat_detections_response_with_next_page}
        )
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": threat_detections_response})

        result = await wiz_threat_detections.single_run()

        assert result == len(threat_detections_response_with_next_page["detections"]["nodes"]) + len(
            threat_detections_response["detections"]["nodes"]
        )

        await wiz_threat_detections._wiz_gql_client.close()


@pytest.mark.asyncio
async def test_wiz_threat_detections_with_duplicates(
    auth_url,
    tenant_url,
    wiz_threat_detections,
    threat_detections_response_with_next_page,
    threat_detections_response,
    http_token,
):
    with aioresponses() as mocked_responses:
        mocked_responses.post(auth_url, status=200, payload=http_token.dict())
        mocked_responses.post(
            tenant_url + "graphql", status=200, payload={"data": threat_detections_response_with_next_page}
        )
        mocked_responses.post(
            tenant_url + "graphql", status=200, payload={"data": threat_detections_response_with_next_page}
        )
        mocked_responses.post(tenant_url + "graphql", status=200, payload={"data": threat_detections_response})

        result = await wiz_threat_detections.single_run()

        assert result == len(threat_detections_response_with_next_page["detections"]["nodes"]) + len(
            threat_detections_response["detections"]["nodes"]
        )

        await wiz_threat_detections._wiz_gql_client.close()
