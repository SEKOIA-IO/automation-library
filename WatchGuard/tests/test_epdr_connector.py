from datetime import datetime
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aioresponses import aioresponses

from watchguard import WatchGuardModule
from watchguard.client.security_event import SecurityEvent
from watchguard.epdr_connector import WatchGuardEpdrConnector

from .helpers import aioresponses_callback


@pytest.fixture
def epdr_connector(module: WatchGuardModule, mock_push_data_to_intakes: AsyncMock) -> WatchGuardEpdrConnector:
    """
    Create an instance of the WatchGuardEpdrConnector with the provided module.

    Args:
        module: The WatchGuard module instance.
        mock_push_data_to_intakes: AsyncMock for pushing data to intakes.

    Returns:
        WatchGuardEpdrConnector: An instance of the WatchGuardEpdrConnector.
    """
    connector = WatchGuardEpdrConnector(module=module)
    connector.push_data_to_intakes = mock_push_data_to_intakes

    return connector


@pytest.mark.asyncio
async def test_epdr_connector(epdr_connector: WatchGuardEpdrConnector, session_faker) -> None:
    response_data = {}
    for security_event in SecurityEvent:
        response_data[security_event] = {
            **session_faker.pydict(value_types=[str, int, float, bool, list, dict]),
            "date": datetime.now().isoformat(),
        }

    auth_token = session_faker.word()
    module_config = epdr_connector.module.configuration
    with aioresponses() as mocked_responses:
        auth_token_url = "{}/oauth/token".format(module_config.base_url)
        mocked_responses.post(
            auth_token_url,
            callback=aioresponses_callback(
                {
                    "access_token": auth_token,
                },
                auth=aiohttp.BasicAuth(module_config.username, module_config.password),
                status=200,
            ),
        )

        for security_event in SecurityEvent:
            data = [
                {
                    **session_faker.pydict(value_types=[str, int]),
                    "date": datetime.now().isoformat(),
                }
                for _ in range(session_faker.random_int(min=1, max=3000))
            ]

            response_data[security_event] = data

            data_url = (
                "{0}/rest/endpoint-security/management/api/v1/accounts/{1}/securityevents/{2}/export/{3}".format(
                    module_config.base_url, module_config.account_id, security_event.value, 1
                )
            )

            mocked_responses.get(
                data_url,
                callback=aioresponses_callback(
                    {"data": data},
                    headers={
                        "WatchGuard-API-Key": module_config.application_key,
                        "Authorization": f"Bearer {auth_token}",
                    },
                    status=200,
                ),
            )

        result = await epdr_connector.get_watchguard_events()
    assert result == sum([len(value) for _, value in response_data.items()])

    await epdr_connector.watchguard_client.close()
