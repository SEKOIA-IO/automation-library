from unittest.mock import Mock

import pytest
from aioresponses import aioresponses

from connectors.azure_entraid_graph_api import AzureEntraIdGraphApiConnector


@pytest.fixture
def entraid_connector(audit_credentials, symphony_storage, mock_push_data_to_intakes) -> AzureEntraIdGraphApiConnector:
    connector = AzureEntraIdGraphApiConnector(data_path=symphony_storage)
    connector.module.configuration = {}
    connector.configuration = {
        "chunk_size": 1,
        "intake_key": "",
        **audit_credentials,
    }
    connector.push_data_to_intakes = mock_push_data_to_intakes
    connector.log_exception = Mock()
    connector.log = Mock()

    return connector


@pytest.mark.asyncio
async def test_entraid_connector_single_run_1(entraid_connector, graph_api_token_url):
    with aioresponses() as mocked_responses:
        mocked_responses.post(
            graph_api_token_url,
            status=200,
            payload={
                "access_token": "test_access_token",
                "expires_in": 3600,
            },
        )

        start_signin = entraid_connector.last_event_date_signin.offset
        signin_url = entraid_connector.client.list_signins_url(start_signin)
        mocked_responses.get(
            url=signin_url,
            status=200,
            payload={
                "value": [
                    {
                        "id": "66ea54eb-6301-4ee5-be62-ff5a759b0100",
                        "createdDateTime": "2023-12-01T16:03:35Z",
                    }
                ],
            },
        )

        start_audit = entraid_connector.last_event_date_directory.offset
        audit_url = entraid_connector.client.list_directory_audits_url(start_audit)
        mocked_responses.get(
            audit_url,
            status=200,
            payload={
                "value": [
                    {
                        "id": "id",
                        "category": "UserManagement",
                        "correlationId": "da159bfb-54fa-4092-8a38-6e1fa7870e30",
                        "result": "success",
                        "resultReason": "Successfully added member to group",
                        "activityDisplayName": "Add member to group",
                        "activityDateTime": "2018-01-09T21:20:02.7215374Z",
                    }
                ]
            },
        )

        result = await entraid_connector.single_run()

        assert result == 2
