from unittest.mock import MagicMock, PropertyMock

import pytest
from sekoia_automation.storage import PersistentJSON

from usta_modules.models import UstaATPConnectorConfiguration, UstaModule, UstaModuleConfig
from usta_modules.usta_atp_connector import UstaAtpConnector


@pytest.fixture
def symphony_storage(tmp_path):
    return tmp_path / "storage.json"


@pytest.fixture
def atp_connector(symphony_storage):
    connector = UstaAtpConnector()
    connector.module = UstaModule()
    connector.module.configuration = UstaModuleConfig(api_key="test_api_key")
    connector.configuration = UstaATPConnectorConfiguration(
        intake_key="intake_key", frequency=60, max_historical_days=1
    )
    connector.log = MagicMock()
    connector.push_events_to_intakes = MagicMock()

    # Mock the running property
    type(connector).running = PropertyMock(side_effect=[True, False])

    connector.context = PersistentJSON(symphony_storage)

    return connector
