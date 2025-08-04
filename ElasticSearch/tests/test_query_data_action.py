from unittest.mock import patch

import pytest

from elasticsearch_module.query_data_action import QueryDataAction, QueryDataArguments


@pytest.fixture(scope="module")
def arguments():
    return QueryDataArguments(
        query="SELECT * FROM some_index",
        drop_null_columns=True,
    )


@pytest.mark.asyncio
async def test_query_data_action(symphony_storage, module, arguments):
    query_data_action = QueryDataAction(module=module, data_path=symphony_storage)

    with (
        patch.object(query_data_action.client, "_query") as mock_query,
        patch.object(query_data_action.client, "_wait_for_result") as mock_wait,
        patch.object(query_data_action.client, "_get_query_result") as mock_get,
        patch.object(query_data_action.client, "_delete_query_result") as mock_delete,
    ):
        mock_query.return_value.body = {"id": "fake-id", "is_running": True}

        mock_get.return_value.body = {"columns": [{"name": "field1"}], "values": [["value1"]]}

        result = query_data_action.run(arguments)

        assert result == {"data": [{"field1": "value1"}]}

        mock_wait.assert_called_once_with("fake-id", timeout=60, drop_null_columns=True)
        mock_delete.assert_called_once_with("fake-id")
