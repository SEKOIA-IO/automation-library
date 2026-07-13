from unittest.mock import AsyncMock, Mock, patch

import asyncio
import httpx
import pytest

from azure_ad.connector_entraid_graph_api import MicrosoftEntraIdGraphApiConnector


@pytest.fixture
def entraid_connector(
    graph_api_client, symphony_storage, mock_push_data_to_intakes
) -> MicrosoftEntraIdGraphApiConnector:
    connector = MicrosoftEntraIdGraphApiConnector(data_path=symphony_storage)
    connector.module.configuration = {
        "tenant_id": "tenant_id",
        "client_id": "client_id",
        "client_secret": "client_secret",
    }
    connector.configuration = {
        "chunk_size": 1,
        "intake_key": "",
    }
    connector.push_data_to_intakes = mock_push_data_to_intakes
    connector._client = graph_api_client
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


@pytest.mark.asyncio
async def test_entraid_connector_async_run_handles_pool_timeout(entraid_connector):
    entraid_connector._stop_event.clear()
    entraid_connector.configuration.frequency = 0
    entraid_connector.single_run = AsyncMock(side_effect=httpx.PoolTimeout("pool timeout"))
    mocked_close = AsyncMock()
    entraid_connector._client.close = mocked_close

    async def fake_sleep(_: int):
        entraid_connector._stop_event.set()

    with patch("azure_ad.connector_entraid_graph_api.asyncio.sleep", new=fake_sleep):
        await entraid_connector.async_run()

    entraid_connector.log_exception.assert_not_called()
    entraid_connector.log.assert_called_once()
    _, kwargs = entraid_connector.log.call_args
    assert kwargs["level"] == "warning"
    assert "PoolTimeout" in kwargs["message"]
    mocked_close.assert_awaited_once()
    assert entraid_connector._client is None


@pytest.mark.asyncio
async def test_entraid_connector_async_run_handles_timeout_exception(entraid_connector):
    entraid_connector._stop_event.clear()
    entraid_connector.configuration.frequency = 0
    entraid_connector.single_run = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mocked_close = AsyncMock()
    entraid_connector._client.close = mocked_close

    async def fake_sleep(_: int):
        entraid_connector._stop_event.set()

    with patch("azure_ad.connector_entraid_graph_api.asyncio.sleep", new=fake_sleep):
        await entraid_connector.async_run()

    entraid_connector.log_exception.assert_not_called()
    entraid_connector.log.assert_called_once()
    _, kwargs = entraid_connector.log.call_args
    assert kwargs["level"] == "warning"
    assert "TimeoutException" in kwargs["message"]
    mocked_close.assert_awaited_once()
    assert entraid_connector._client is None


@pytest.mark.asyncio
async def test_entraid_connector_async_run_handles_asyncio_timeout(entraid_connector):
    entraid_connector._stop_event.clear()
    entraid_connector.configuration.frequency = 0
    entraid_connector.single_run = AsyncMock(side_effect=asyncio.TimeoutError("asyncio timeout"))
    mocked_close = AsyncMock()
    entraid_connector._client.close = mocked_close

    async def fake_sleep(_: int):
        entraid_connector._stop_event.set()

    with patch("azure_ad.connector_entraid_graph_api.asyncio.sleep", new=fake_sleep):
        await entraid_connector.async_run()

    entraid_connector.log_exception.assert_not_called()
    entraid_connector.log.assert_called_once()
    _, kwargs = entraid_connector.log.call_args
    assert kwargs["level"] == "warning"
    assert "TimeoutError" in kwargs["message"]
    mocked_close.assert_awaited_once()
    assert entraid_connector._client is None


@pytest.mark.asyncio
async def test_entraid_connector_reset_graph_client_with_client(entraid_connector):
    mocked_close = AsyncMock()
    entraid_connector._client.close = mocked_close

    await entraid_connector._reset_graph_client()

    mocked_close.assert_awaited_once()
    assert entraid_connector._client is None


@pytest.mark.asyncio
async def test_entraid_connector_reset_graph_client_without_client(entraid_connector):
    entraid_connector._client = None

    await entraid_connector._reset_graph_client()

    assert entraid_connector._client is None
