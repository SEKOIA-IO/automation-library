import time
from multiprocessing import Process
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinelone_module.base import SentinelOneModule
from sentinelone_module.singularity.connectors import AbstractSingularityConnector


class CustomTestConnector(AbstractSingularityConnector):
    product_name = "test_product"


@pytest.fixture
def custom_test_connector(
    sentinel_module: SentinelOneModule, mock_push_data_to_intakes: AsyncMock
) -> CustomTestConnector:
    connector = CustomTestConnector(sentinel_module)
    connector.configuration = {
        "intake_key": "test_key",
        "intake_server": "http://test_server.test",
        "frequency": 3,
    }
    connector.push_data_to_intakes = mock_push_data_to_intakes

    return connector


def patch_connector(
    connector: AbstractSingularityConnector, expected_number_of_alerts: int
) -> AbstractSingularityConnector:
    def gql_return_values(query, variable_values) -> dict[str, Any]:
        alert = {"id": "test_id", "detectedAt": "2022-01-01T00:00:00Z"}

        if variable_values["after"] is None:
            return {
                "alerts": {
                    "totalCount": 1,
                    "pageInfo": {"endCursor": "cursor", "hasNextPage": True},
                    "edges": [{"node": alert} for _ in range(expected_number_of_alerts - 2)],
                }
            }

        return {
            "alerts": {
                "totalCount": 0,
                "pageInfo": {"endCursor": "cursor-1", "hasNextPage": False},
                "edges": [{"node": alert}, {"node": alert}],
            }
        }

    graphql = MagicMock()
    graphql.execute_async = AsyncMock(side_effect=gql_return_values)
    connector.client._client = graphql

    return connector


@pytest.mark.asyncio
async def test_single_run_connector(custom_test_connector: CustomTestConnector):
    expected_number_of_alerts = 10
    patched_connector = patch_connector(custom_test_connector, expected_number_of_alerts)

    result = await patched_connector.single_run()
    assert result == expected_number_of_alerts
