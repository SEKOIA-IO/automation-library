from unittest.mock import Mock

import pytest

from connectors.azure_entraid_graph_api import AzureEntraIdGraphApiConnector


@pytest.fixture
def entraid_connector(client, symphony_storage, mock_push_data_to_intakes) -> AzureEntraIdGraphApiConnector:
    connector = AzureEntraIdGraphApiConnector(data_path=symphony_storage)
    connector.module.configuration = {}
    connector.configuration = {
        "chunk_size": 1,
        "intake_key": "",
        "tenant_id": "tenant_id",
        "client_id": "client_id",
        "client_secret": "client_secret",
    }
    connector.push_data_to_intakes = mock_push_data_to_intakes
    connector._client = client
    connector.log_exception = Mock()
    connector.log = Mock()

    return connector


@pytest.mark.asyncio
async def test_entraid_connector_single_run_1(
    entraid_connector, signins_page_1, signins_page_2, directory_audits_page_1, directory_audits_page_2
):
    entraid_connector._client._client.audit_logs.sign_ins.get.return_value = signins_page_1
    entraid_connector._client._client.audit_logs.sign_ins.with_url.return_value.get.return_value = signins_page_2
    entraid_connector._client._client.audit_logs.directory_audits.get.return_value = directory_audits_page_1
    entraid_connector._client._client.audit_logs.directory_audits.with_url.return_value.get.return_value = (
        directory_audits_page_2
    )

    result = await entraid_connector.single_run()
    assert result == 6


@pytest.mark.asyncio
async def test_entraid_connector_single_run_2(
    entraid_connector, signins_page_1, signins_page_2, directory_audits_page_1, directory_audits_page_2
):
    entraid_connector.configuration.chunk_size = 3

    entraid_connector._client._client.audit_logs.sign_ins.get.return_value = signins_page_1
    entraid_connector._client._client.audit_logs.sign_ins.with_url.return_value.get.return_value = signins_page_2
    entraid_connector._client._client.audit_logs.directory_audits.get.return_value = directory_audits_page_1
    entraid_connector._client._client.audit_logs.directory_audits.with_url.return_value.get.return_value = (
        directory_audits_page_2
    )

    entraid_connector.signin_cache["1"] = True
    entraid_connector.directory_alerts_cache["3"] = True

    result = await entraid_connector.single_run()

    assert result == 4
