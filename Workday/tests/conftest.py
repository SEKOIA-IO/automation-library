"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from faker import Faker
from types import SimpleNamespace


@pytest.fixture
def faker():
    """Provide a Faker instance."""
    return Faker()


@pytest.fixture
def mock_data_path(tmp_path):
    """Create a temporary data path for tests."""
    return tmp_path


@pytest.fixture
def activity_logging_connector(mock_data_path):
    """Create a WorkdayActivityLoggingConnector instance with mocked dependencies."""
    from workday.workday_activity_logging_connector import (
        WorkdayActivityLoggingConnector,
        WorkdayActivityLoggingConfiguration,
    )

    # Create a mock module and a simple configuration object so attribute access is predictable
    mock_module = MagicMock()
    mock_module.configuration = SimpleNamespace(
        workday_host="wd3-services1.myworkday.com",
        tenant_name="test_tenant",
        client_id="test_client_id",
        client_secret="test_client_secret",
        refresh_token="test_refresh_token",
    )

    # FIXED: The framework calls module.load_config(config_class, config_data_to_load)
    # Since it's a bound method on the mock, we need to accept the config_class parameter
    # The MagicMock will handle the self parameter automatically
    mock_module.load_config = MagicMock(
        return_value=WorkdayActivityLoggingConfiguration(
            intake_key="test_intake_key", frequency=600, chunk_size=1000, limit=1000
        )
    )

    # Create connector instance
    connector = WorkdayActivityLoggingConnector(module=mock_module, data_path=mock_data_path)

    # Mock push_data_to_intakes
    connector.push_data_to_intakes = AsyncMock()
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    return connector
