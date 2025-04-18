from unittest.mock import patch

import pytest

from elasticsearch_module import ElasticSearchClient
from elasticsearch_module.client import ElasticSearchApiError, ElasticSearchError


@pytest.fixture(scope="session")
def elasticsearch_client(elasticsearch_url, api_key) -> ElasticSearchClient:
    return ElasticSearchClient(
        url=elasticsearch_url,
        api_key=api_key,
    )


@pytest.mark.asyncio
async def test_execute_query_simple_1(elasticsearch_client):
    with (
        patch.object(elasticsearch_client, "_query") as mock_query,
        patch.object(elasticsearch_client, "_wait_for_result") as mock_wait,
        patch.object(elasticsearch_client, "_get_query_result") as mock_get,
        patch.object(elasticsearch_client, "_delete_query_result") as mock_delete,
    ):

        mock_query.return_value.body = {
            "id": "fake-id",
            "is_running": False,
            "columns": [{"name": "field1"}],
            "values": [["value1"]],
        }

        result = elasticsearch_client.execute_esql_query("SELECT 123 FROM index")

        assert result == [{"field1": "value1"}]

        mock_wait.assert_not_called()
        mock_delete.assert_called_once_with("fake-id")


@pytest.mark.asyncio
async def test_execute_query_simple_2(elasticsearch_client):
    with (
        patch.object(elasticsearch_client, "_query") as mock_query,
        patch.object(elasticsearch_client, "_wait_for_result") as mock_wait,
        patch.object(elasticsearch_client, "_get_query_result") as mock_get,
        patch.object(elasticsearch_client, "_delete_query_result") as mock_delete,
    ):

        mock_query.return_value.body = {"is_running": False, "columns": [{"name": "field1"}], "values": [["value1"]]}

        result = elasticsearch_client.execute_esql_query("SELECT 123 FROM index")

        assert result == [{"field1": "value1"}]

        mock_wait.assert_not_called()
        mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_execute_query_no_id(elasticsearch_client):
    with (
        patch.object(elasticsearch_client, "_query") as mock_query,
        patch.object(elasticsearch_client, "_wait_for_result") as mock_wait,
        patch.object(elasticsearch_client, "_get_query_result") as mock_get,
        patch.object(elasticsearch_client, "_delete_query_result") as mock_delete,
    ):

        mock_query.return_value.body = {
            "is_running": True,
        }

        with pytest.raises(ElasticSearchError):
            elasticsearch_client.execute_esql_query("SELECT 123 FROM index")


@pytest.mark.asyncio
async def test_execute_query_error(elasticsearch_client):
    with (
        patch.object(elasticsearch_client, "_query") as mock_query,
        patch.object(elasticsearch_client, "_get_query_result") as mock_get,
        patch.object(elasticsearch_client, "_delete_query_result") as mock_delete,
    ):

        mock_query.return_value.body = {
            "id": "fake-id",
            "is_running": True,
        }

        mock_get.return_value.body = {
            "error": {"reason": "An error occurred", "type": "query_error", "index": "my-index"},
            "status": 404,
        }

        with pytest.raises(ElasticSearchApiError):
            elasticsearch_client.execute_esql_query("SELECT 123 FROM index")


@pytest.mark.asyncio
async def test_execute_query_full(elasticsearch_client):
    with (
        patch.object(elasticsearch_client, "_query") as mock_query,
        patch.object(elasticsearch_client, "_wait_for_result") as mock_wait,
        patch.object(elasticsearch_client, "_get_query_result") as mock_get,
        patch.object(elasticsearch_client, "_delete_query_result") as mock_delete,
    ):

        mock_query.return_value.body = {"id": "fake-id", "is_running": True}

        mock_get.return_value.body = {"columns": [{"name": "field1"}], "values": [["value1"]]}

        result = elasticsearch_client.execute_esql_query("SELECT field1 FROM index")

        assert result == [{"field1": "value1"}]

        mock_wait.assert_called_once_with("fake-id")
        mock_delete.assert_called_once_with("fake-id")
