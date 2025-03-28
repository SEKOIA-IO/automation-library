from unittest.mock import patch

import pytest
from azure.monitor.query import LogsQueryResult, LogsQueryStatus, LogsTable

from azure_monitor_modules import AzureMonitorModule
from azure_monitor_modules.action_query import AzureMonitorQueryAction, AzureMonitorQueryArguments


@pytest.fixture()
def azure_monitor_module():
    module = AzureMonitorModule()
    module.configuration = {
        "tenant_id": "azefazefazegazetazeytazeyaze",
        "client_id": "e139c076-122f-4c2e-9d0d-azefazegazeg",
        "client_secret": "client_secret",
    }
    return module


@pytest.fixture
def arguments():
    return AzureMonitorQueryArguments(
        query="SecurityIncident | take 5", workspace_id="f9692feb-5f5f-4461-8bc2-a46928eaa527"
    )


def test_query(data_storage, azure_monitor_module, arguments):
    with patch("azure_monitor_modules.action_base.AzureMonitorBaseAction.client") as mock_logs_query_client:
        fake_table = LogsTable(
            name="MockTable",
            columns=["timestamp", "message"],
            columns_types=["datetime", "string"],
            rows=[["2024-03-10T12:00:00Z", "Test log entry 1"], ["2024-03-10T12:05:00Z", "Test log entry 2"]],
        )

        fake_response = LogsQueryResult(tables=[fake_table])
        fake_response.status = LogsQueryStatus.SUCCESS

        mock_logs_query_client.query_workspace.return_value = fake_response

        action = AzureMonitorQueryAction(module=azure_monitor_module, data_path=data_storage)
        result = action.run(arguments)

        assert result == {
            "data": [
                {
                    "name": "MockTable",
                    "records": [
                        {"timestamp": "2024-03-10T12:00:00Z", "message": "Test log entry 1"},
                        {"timestamp": "2024-03-10T12:05:00Z", "message": "Test log entry 2"},
                    ],
                }
            ]
        }
