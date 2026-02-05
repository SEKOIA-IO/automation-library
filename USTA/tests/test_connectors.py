import json
from typing import Any, List, Dict
from unittest.mock import patch, PropertyMock

import pytest

from usta_modules.usta_atp_connector import UstaAPIError, UstaAtpConnector
from usta_modules.usta_sdk import UstaAuthenticationError


class StopTest(Exception):
    """Custom exception used to break the infinite run loop during testing."""

    pass


def test_happy_path(atp_connector: UstaAtpConnector, sample_events: List[Dict[str, Any]]) -> None:
    """Tests the end-to-end success scenario.

    Verifies that the connector correctly fetches events from the API,
    logs the progress, and pushes the data to the Sekoia intake.

    Args:
        atp_connector (UstaAtpConnector): The connector instance fixture.
        sample_events (List[Dict[str, Any]]): The sample event data fixture.
    """
    expected_events = [json.dumps(event) for event in sample_events]

    with (
        patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client,
        patch("time.sleep", side_effect=StopTest),
    ):
        mock_instance = mock_usta_client.return_value
        mock_instance.iter_compromised_credentials.return_value = sample_events

        try:
            atp_connector.run()
        except StopTest:
            pass

        # Verify events were pushed
        atp_connector.push_events_to_intakes.assert_called_once_with(
            events=expected_events,
        )

        # Verify logs
        atp_connector.log.assert_any_call(message=f"{len(sample_events)} events collected", level="info")
        atp_connector.log.assert_any_call(message="Events pushed to intakes!", level="info")


def test_forward_empty_list_of_events(atp_connector: UstaAtpConnector) -> None:
    """Tests that nothing is pushed when the API returns an empty list.

    Args:
        atp_connector (UstaAtpConnector): The connector instance fixture.
    """
    with (
        patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client,
        patch("time.sleep", side_effect=StopTest),
    ):
        mock_instance = mock_usta_client.return_value
        mock_instance.iter_compromised_credentials.return_value = []

        try:
            atp_connector.run()
        except StopTest:
            pass

        atp_connector.push_events_to_intakes.assert_not_called()


def test_missing_api_key(atp_connector: UstaAtpConnector) -> None:
    """Tests that a ValueError is raised when the API key is missing.

    Args:
        atp_connector (UstaAtpConnector): The connector instance fixture.
    """
    atp_connector.module.configuration.api_key = ""

    with pytest.raises(ValueError) as excinfo:
        atp_connector.run()

    assert "Authorization token must be provided." in str(excinfo.value)
    atp_connector.push_events_to_intakes.assert_not_called()


def test_connector_polling_logs(atp_connector: UstaAtpConnector) -> None:
    """Tests that the initial polling log messages are emitted correctly.

    Args:
        atp_connector (UstaAtpConnector): The connector instance fixture.
    """
    # Note: running=True is already set in conftest.py
    with (
        patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client,
        patch("time.sleep", side_effect=StopTest),
    ):
        mock_usta_client.return_value.iter_compromised_credentials.return_value = []

        try:
            atp_connector.run()
        except StopTest:
            pass

        atp_connector.log.assert_any_call(message="Polling USTA security intelligence API...", level="info")


def test_connector_api_error_handling(atp_connector: UstaAtpConnector) -> None:
    """Tests that the connector handles API errors gracefully without crashing.

    Verifies that a `UstaAPIError` is logged as an error and the loop continues
    (reaches time.sleep/StopTest) instead of raising an unhandled exception.

    Args:
        atp_connector (UstaAtpConnector): The connector instance fixture.
    """
    with (
        patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client,
        patch("time.sleep", side_effect=StopTest),
    ):
        mock_usta_client.return_value.iter_compromised_credentials.side_effect = UstaAPIError("Connection Timeout")

        try:
            atp_connector.run()
        except StopTest:
            pass

        atp_connector.log.assert_any_call(message="USTA-SDK Error: Connection Timeout", level="error")
        atp_connector.push_events_to_intakes.assert_not_called()


def test_connector_auth_error_raises(atp_connector: UstaAtpConnector) -> None:
    """Tests that an Authentication Error raises an exception and stops the connector.

    Authentication errors are considered critical and should not be retried silently.

    Args:
        atp_connector (UstaAtpConnector): The connector instance fixture.
    """
    with patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client:
        mock_usta_client.return_value.iter_compromised_credentials.side_effect = UstaAuthenticationError(
            "Invalid API Key"
        )

        with pytest.raises(UstaAuthenticationError):
            atp_connector.run()

        atp_connector.log.assert_any_call(message="USTA Authentication Error: Invalid API Key", level="critical")


def test_run_loop_exits_gracefully(atp_connector: UstaAtpConnector) -> None:
    """Tests that the connector exits the run loop gracefully when `running` becomes False.

    This ensures 100% code coverage by verifying the loop termination logic.
    We override the `running` property to simulate a sequence: [True, True, False].

    Args:
        atp_connector (UstaAtpConnector): The connector instance fixture.
    """
    with patch.object(UstaAtpConnector, "running", new_callable=PropertyMock) as mock_running:
        # Sequence: [True (Log read), True (While check), False (While check exit)]
        mock_running.side_effect = [True, True, False]

        with (
            patch("usta_modules.usta_atp_connector.UstaClient"),
            patch("time.sleep") as mock_sleep,  # Do not raise exception, just pass
        ):
            atp_connector.run()

            # The loop should execute once and then exit, calling sleep exactly once.
            assert mock_sleep.call_count == 1
