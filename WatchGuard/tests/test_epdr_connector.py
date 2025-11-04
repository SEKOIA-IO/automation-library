from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses

from watchguard import WatchGuardModule
from watchguard.client.security_event import SecurityEvent
from watchguard.epdr_connector import WatchGuardEpdrConnector

from .helpers import aioresponses_callback


@pytest.fixture
def epdr_connector(module: WatchGuardModule, mock_push_data_to_intakes: AsyncMock, symphony_storage: Path) -> WatchGuardEpdrConnector:
    """
    Create an instance of the WatchGuardEpdrConnector with the provided module.

    Args:
        module: The WatchGuard module instance.
        mock_push_data_to_intakes: AsyncMock for pushing data to intakes.
        symphony_storage: Path to the temporary storage directory.

    Returns:
        WatchGuardEpdrConnector: An instance of the WatchGuardEpdrConnector.
    """
    connector = WatchGuardEpdrConnector(module=module, data_path=symphony_storage)
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


@pytest.mark.asyncio
async def test_epdr_connector_incidents(epdr_connector: WatchGuardEpdrConnector, session_faker) -> None:
    """
    Test the incident fetching functionality of the WatchGuardEpdrConnector.
    
    Args:
        epdr_connector: The WatchGuardEpdrConnector instance
        session_faker: Faker instance for generating test data
    """
    # Generate fake incident data
    incident_data = [
        {
            **session_faker.pydict(value_types=[str, int]),
            "date": datetime.now().isoformat(),
            "id": session_faker.uuid4(),
        }
        for _ in range(session_faker.random_int(min=1, max=10))
    ]

    auth_token = session_faker.word()
    module_config = epdr_connector.module.configuration
    
    with aioresponses() as mocked_responses:
        # Mock auth token endpoint
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

        # Mock incidents endpoint (using None as incident_id to get all incidents)
        incidents_url = "{0}/rest/threatsync/management/v1/{1}/incidents/{2}".format(
            module_config.base_url, module_config.account_id, None
        )

        mocked_responses.get(
            incidents_url,
            callback=aioresponses_callback(
                {"data": incident_data},
                headers={
                    "WatchGuard-API-Key": module_config.application_key,
                    "Authorization": f"Bearer {auth_token}",
                },
                status=200,
            ),
        )

        # Test the incident fetching
        result = await epdr_connector.get_watchguard_incidents()
        
    assert result == len(incident_data)
    await epdr_connector.watchguard_client.close()


@pytest.mark.asyncio
async def test_last_incident_date_no_cache(epdr_connector: WatchGuardEpdrConnector) -> None:
    """
    Test last_incident_date when no cached date exists.
    
    Args:
        epdr_connector: The WatchGuardEpdrConnector instance
    """
    # Clear any existing cache
    with epdr_connector.context as cache:
        cache.clear()
    
    last_date = epdr_connector.last_incident_date()
    
    # Should return one day ago when no cache exists
    from datetime import datetime, timedelta, timezone
    expected_date = (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0)
    
    # Allow for small time differences (within 1 minute)
    assert abs((last_date - expected_date).total_seconds()) < 60


@pytest.mark.asyncio
async def test_last_incident_date_with_cache(epdr_connector: WatchGuardEpdrConnector) -> None:
    """
    Test last_incident_date when cached date exists and is recent.
    
    Args:
        epdr_connector: The WatchGuardEpdrConnector instance
    """
    from datetime import datetime, timedelta, timezone
    
    # Set a cached date from 2 hours ago
    cached_date = datetime.now(timezone.utc) - timedelta(hours=2)
    
    with epdr_connector.context as cache:
        cache["incidents"] = cached_date.isoformat()
    
    last_date = epdr_connector.last_incident_date()
    
    # Should return the cached date since it's within the last day
    expected_date = cached_date.replace(microsecond=0)
    assert last_date == expected_date


@pytest.mark.asyncio
async def test_last_incident_date_old_cache(epdr_connector: WatchGuardEpdrConnector) -> None:
    """
    Test last_incident_date when cached date is older than 1 day (fallback behavior).
    
    Args:
        epdr_connector: The WatchGuardEpdrConnector instance
    """
    from datetime import datetime, timedelta, timezone
    
    # Set a cached date from 5 days ago (older than the 1-day limit)
    old_cached_date = datetime.now(timezone.utc) - timedelta(days=5)
    
    with epdr_connector.context as cache:
        cache["incidents"] = old_cached_date.isoformat()
    
    last_date = epdr_connector.last_incident_date()
    
    # Should return one day ago (not the old cached date) due to max() logic
    expected_date = (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0)
    
    # Allow for small time differences (within 1 minute)
    assert abs((last_date - expected_date).total_seconds()) < 60


@pytest.mark.asyncio
async def test_epdr_connector_incidents_empty_response(epdr_connector: WatchGuardEpdrConnector, session_faker) -> None:
    """
    Test incident fetching when API returns empty data.
    
    Args:
        epdr_connector: The WatchGuardEpdrConnector instance
        session_faker: Faker instance for generating test data
    """
    auth_token = session_faker.word()
    module_config = epdr_connector.module.configuration
    
    with aioresponses() as mocked_responses:
        # Mock auth token endpoint
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

        # Mock incidents endpoint with empty data
        incidents_url = "{0}/rest/threatsync/management/v1/{1}/incidents/{2}".format(
            module_config.base_url, module_config.account_id, None
        )

        mocked_responses.get(
            incidents_url,
            callback=aioresponses_callback(
                {"data": []},  # Empty data array
                headers={
                    "WatchGuard-API-Key": module_config.application_key,
                    "Authorization": f"Bearer {auth_token}",
                },
                status=200,
            ),
        )

        # Test the incident fetching
        result = await epdr_connector.get_watchguard_incidents()
        
    assert result == 0  # Should return 0 for empty data
    await epdr_connector.watchguard_client.close()
