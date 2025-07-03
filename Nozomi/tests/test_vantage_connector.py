from datetime import datetime
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from aioresponses import aioresponses
from faker.proxy import Faker
from loguru import logger

from nozomi_networks import NozomiModule
from nozomi_networks.client.event_type import EventType
from nozomi_networks.client.http_client import NozomiClient
from nozomi_networks.nozomi_vantage_connector import NozomiVantageConfiguration, NozomiVantageConnector

from .helpers import aioresponses_callback


@pytest.fixture
def vantage_connector(
    module: NozomiModule, mock_push_data_to_intakes: AsyncMock, session_faker: Faker
) -> NozomiVantageConnector:
    """
    Create an instance of the NozomiVantageConnector with the provided module.

    Args:
        module: The Nozomi module instance.
        mock_push_data_to_intakes: AsyncMock for pushing data to intakes.
        session_faker: Faker instance for generating fake data.

    Returns:
        NozomiVantageConnector: An instance of the NozomiVantageConnector.
    """
    connector = NozomiVantageConnector(module=module)
    connector.configuration = NozomiVantageConfiguration(
        intake_key=session_faker.word(),
        batch_size=3,
    )
    connector.push_data_to_intakes = mock_push_data_to_intakes

    return connector


@pytest.mark.asyncio
async def test_vantage_connector(vantage_connector: NozomiVantageConnector, session_faker) -> None:
    response_data = {}
    for event_type in EventType:
        response_data[event_type] = [
            {
                "id": session_faker.uuid4(),
                "type": event_type.value,
                "attributes": {
                    **session_faker.pydict(value_types=[str, int, float, bool]),
                    "time": datetime.now().timestamp() * 1000,  # Convert to milliseconds
                },
            }
            for _ in range(100)  # Generate 10,000 events for each type
        ]

    auth_token = session_faker.word()
    module_config = vantage_connector.module.configuration
    with aioresponses() as mocked_responses:
        auth_token_url = "{}/api/v1/keys/sign_in".format(module_config.base_url)
        mocked_responses.post(
            auth_token_url,
            callback=aioresponses_callback(
                {},
                response_headers={
                    "Authorization": f"Bearer {auth_token}",
                },
                status=200,
            ),
        )

        for event_type in EventType:
            start_date = vantage_connector.last_event_date(event_type)

            base_params = NozomiClient._get_filters(event_type, start_date)

            encoded_params_1 = urlencode({"page": 1, "size": 100, **base_params})
            data_url_1 = f"{module_config.base_url}/api/v1/{event_type.value}?{encoded_params_1}"
            logger.info(f"Data URL: {data_url_1}")
            mocked_responses.get(
                data_url_1,
                payload={"data": response_data[event_type]},
            )

            encoded_params_2 = urlencode({"page": 2, "size": 100, **base_params})
            data_url_2 = f"{module_config.base_url}/api/v1/{event_type.value}?{encoded_params_2}"
            mocked_responses.get(
                data_url_2,
                payload={"data": []},
            )

        result = await vantage_connector.get_events()

    assert result == sum([len(value) for _, value in response_data.items()])

    await vantage_connector.nozomi_client.close()
