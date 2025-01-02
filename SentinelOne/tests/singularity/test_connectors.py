import itertools
import time
from pathlib import Path
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
    sentinel_module: SentinelOneModule, symphony_storage: Path, mock_push_data_to_intakes: AsyncMock
) -> CustomTestConnector:
    connector = CustomTestConnector(module=sentinel_module, data_path=symphony_storage)
    connector.configuration = {
        "intake_key": "test_key",
        "intake_server": "http://test_server.test",
        "frequency": 3,
    }
    connector.push_data_to_intakes = mock_push_data_to_intakes

    return connector


def patch_connector(connector: AbstractSingularityConnector, alert_ids: list) -> AbstractSingularityConnector:

    alerts_count = len(alert_ids)
    first_page = itertools.islice(alert_ids, 0, alerts_count - 2)
    second_page = itertools.islice(alert_ids, alerts_count - 2, alerts_count)

    def gql_return_values(query, variable_values) -> dict[str, Any]:
        if variable_values["after"] is None:
            return {
                "alerts": {
                    "totalCount": 1,
                    "pageInfo": {"endCursor": "cursor", "hasNextPage": True},
                    "edges": [
                        {"node": {"id": alert_id, "detectedAt": "2022-01-01T00:00:00Z"}} for alert_id in first_page
                    ],
                }
            }

        return {
            "alerts": {
                "totalCount": 0,
                "pageInfo": {"endCursor": None, "hasNextPage": False},
                "edges": [
                    {"node": {"id": alert_id, "detectedAt": "2022-01-01T00:00:00Z"}} for alert_id in second_page
                ],
            }
        }

    graphql = MagicMock()
    graphql.execute_async = AsyncMock(side_effect=gql_return_values)
    connector.client._client = graphql

    return connector


@pytest.mark.asyncio
async def test_single_run_connector(custom_test_connector: CustomTestConnector):
    alert_ids = [f"alert{index}" for index in range(10)]
    patched_connector = patch_connector(custom_test_connector, alert_ids)

    result = await patched_connector.single_run()
    assert result == 10


@pytest.mark.asyncio
async def test_single_run_connector_discard_already_collected_alerts(custom_test_connector: CustomTestConnector):
    alert_ids = ["alert1", "alert2", "alert3", "alert1", "alert4", "alert2"]
    patched_connector = patch_connector(custom_test_connector, alert_ids)

    result = await patched_connector.single_run()
    assert result == 4
