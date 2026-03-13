from pathlib import Path
from typing import Any, List, Dict
from unittest.mock import MagicMock, PropertyMock

import pytest
from sekoia_automation.storage import PersistentJSON

from usta_modules.models import UstaATPConnectorConfiguration, UstaModule, UstaModuleConfig
from usta_modules.usta_atp_connector import UstaAtpConnector
from usta_modules.usta_sdk import UstaClient


@pytest.fixture
def sample_events() -> List[Dict[str, Any]]:
    """Provides a standard dataset of USTA events for testing.

    Returns:
        List[Dict[str, Any]]: A list containing a representative compromised credential event.
    """
    return [
        {
            "company": {"id": 0, "name": "string"},
            "content": {
                "is_corporate": True,
                "password": "string",
                "password_complexity": {
                    "contains": {
                        "lowercase": 0,
                        "numbers": 0,
                        "other": 0,
                        "punctuation": 0,
                        "separators": 0,
                        "symbols": 0,
                        "uppercase": 0,
                    },
                    "length": 0,
                    "score": "very_weak",
                },
                "source": "malware",
                "url": "http://example.com",
                "username": "string",
                "victim_detail": {
                    "computer_name": "string",
                    "country": "string",
                    "cpu": "string",
                    "gpu": "string",
                    "infection_date": "string",
                    "ip": "string",
                    "language": "string",
                    "malware": "string",
                    "memory": "string",
                    "phone_number": "string",
                    "username": "string",
                    "victim_os": "string",
                    "victim_uid": "9eee4f4d-714d-402f-b9c1-17d4442e0901",
                },
            },
            "content_type": "string",
            "created": "2019-08-24T14:15:22Z",
            "id": 0,
            "status": "in_progress",
            "status_timestamp": "2019-08-24T14:15:22Z",
        }
    ]


@pytest.fixture
def symphony_storage(tmp_path: Path) -> Path:
    """Creates a temporary storage file for the connector context.

    Args:
        tmp_path (Path): Pytest fixture for temporary directories.

    Returns:
        Path: The path to the `storage.json` file.
    """
    return tmp_path / "storage.json"


@pytest.fixture
def usta_client(symphony_storage: Path) -> UstaClient:
    """Creates an instance of UstaClient with a mock token.

    Args:
        symphony_storage (Path): The temporary storage path (unused here but ensures order).

    Returns:
        UstaClient: An initialized UstaClient instance.
    """
    return UstaClient(token="fake-token")


@pytest.fixture
def atp_connector(symphony_storage: Path) -> UstaAtpConnector:
    """Creates a configured UstaAtpConnector instance with mocked IO methods.

    This fixture initializes the connector, sets up a mock configuration,
    and mocks the `log` and `push_events_to_intakes` methods to prevent
    actual side effects. It also forces the `running` property to return True.

    Args:
        symphony_storage (Path): The temporary storage path for the connector context.

    Returns:
        UstaAtpConnector: A ready-to-test connector instance.
    """
    connector = UstaAtpConnector()
    connector.module = UstaModule()
    connector.module.configuration = UstaModuleConfig(api_key="test_api_key")

    connector.configuration = UstaATPConnectorConfiguration(
        intake_key="intake_key", frequency=60, max_historical_days=1
    )

    connector.log = MagicMock()
    connector.push_events_to_intakes = MagicMock()

    # Mock the running property to ensure the loop can start
    type(connector).running = PropertyMock(return_value=True)

    connector.context = PersistentJSON(symphony_storage)

    return connector
