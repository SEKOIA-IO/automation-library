import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from usta_modules.usta_atp_connector import UstaAPIError, UstaAtpConnector, parse_created
from usta_modules.usta_sdk import UstaAuthenticationError


class StopTestError(Exception):
    """Custom exception used to break the infinite run loop during testing."""

    pass


def test_happy_path(atp_connector: UstaAtpConnector, sample_events: list[dict[str, Any]]) -> None:
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
        patch("time.sleep", side_effect=StopTestError),
    ):
        mock_instance = mock_usta_client.return_value
        mock_instance.iter_compromised_credentials.return_value = sample_events

        try:
            atp_connector.run()
        except StopTestError:
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
        patch("time.sleep", side_effect=StopTestError),
    ):
        mock_instance = mock_usta_client.return_value
        mock_instance.iter_compromised_credentials.return_value = []

        try:
            atp_connector.run()
        except StopTestError:
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
        patch("time.sleep", side_effect=StopTestError),
    ):
        mock_usta_client.return_value.iter_compromised_credentials.return_value = []

        try:
            atp_connector.run()
        except StopTestError:
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
        patch("time.sleep", side_effect=StopTestError),
    ):
        mock_usta_client.return_value.iter_compromised_credentials.side_effect = UstaAPIError("Connection Timeout")

        try:
            atp_connector.run()
        except StopTestError:
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


# ──────────────────────────────────────────────────────────────────────────
# Checkpoint
# ──────────────────────────────────────────────────────────────────────────
def _run_until_sleep(connector: UstaAtpConnector, pages: list[list[dict[str, Any]]]) -> Any:
    """Run the connector for `len(pages)` polls, each poll returning the given events."""
    sleeps: list[Any] = [None] * (len(pages) - 1) + [StopTestError]
    with (
        patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client,
        patch("time.sleep", side_effect=sleeps),
    ):
        mock_instance = mock_usta_client.return_value
        mock_instance.iter_compromised_credentials.side_effect = [iter(page) for page in pages]
        with pytest.raises(StopTestError):
            connector.run()
    return mock_instance


def _read_checkpoint(data_storage: Path) -> datetime | None:
    context = data_storage / "context.json"
    if not context.exists():
        return None
    value = json.loads(context.read_text()).get("most_recent_date_seen")
    return datetime.fromisoformat(value) if value else None


def test_parse_created() -> None:
    assert parse_created("2026-10-26T10:00:00Z") == datetime(2026, 10, 26, 10, tzinfo=UTC)
    assert parse_created("2026-10-26T12:00:00.123456+02:00") == datetime(2026, 10, 26, 10, 0, 0, 123456, tzinfo=UTC)
    assert parse_created("2026-10-26T10:00:00") == datetime(2026, 10, 26, 10, tzinfo=UTC)
    assert parse_created("not a date") is None
    assert parse_created(None) is None


def test_first_run_starts_at_max_historical_days(atp_connector: UstaAtpConnector, data_storage: Path) -> None:
    before = datetime.now(UTC)
    mock_instance = _run_until_sleep(atp_connector, [[]])

    start = datetime.fromisoformat(mock_instance.iter_compromised_credentials.call_args.kwargs["start"])
    assert before - timedelta(days=1, seconds=5) <= start <= datetime.now(UTC) - timedelta(days=1)
    assert mock_instance.iter_compromised_credentials.call_args.kwargs["ordering"] == ["created"]
    # nothing collected: no checkpoint persisted
    assert _read_checkpoint(data_storage) is None


def test_cursor_advances_to_most_recent_created(atp_connector: UstaAtpConnector, data_storage: Path) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    newest = now - timedelta(minutes=5)
    events = [
        {"id": 1, "created": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")},
        {"id": 2, "created": newest.astimezone(timezone(timedelta(hours=2))).isoformat()},
        {"id": 3, "created": (now - timedelta(hours=1)).isoformat()},
        {"id": 4, "created": "invalid"},
    ]

    _run_until_sleep(atp_connector, [events])

    atp_connector.push_events_to_intakes.assert_called_once_with(events=[json.dumps(e) for e in events])
    assert _read_checkpoint(data_storage) == newest
    assert atp_connector.cursor.offset == newest


def test_resume_from_checkpoint_after_restart(atp_connector: UstaAtpConnector, data_storage: Path) -> None:
    checkpoint = (datetime.now(UTC) - timedelta(hours=3)).replace(microsecond=123456)
    (data_storage / "context.json").write_text(json.dumps({"most_recent_date_seen": checkpoint.isoformat()}))

    mock_instance = _run_until_sleep(atp_connector, [[]])

    assert mock_instance.iter_compromised_credentials.call_args.kwargs["start"] == checkpoint.isoformat()


def test_restarted_connector_resumes_where_previous_one_stopped(
    atp_connector: UstaAtpConnector, data_storage: Path
) -> None:
    created = (datetime.now(UTC) - timedelta(minutes=10)).replace(microsecond=0)
    _run_until_sleep(atp_connector, [[{"id": 1, "created": created.isoformat()}]])

    restarted = UstaAtpConnector(data_path=data_storage)
    restarted.module = atp_connector.module
    restarted.configuration = atp_connector.configuration
    restarted.log = MagicMock()
    restarted.push_events_to_intakes = MagicMock()
    mock_instance = _run_until_sleep(restarted, [[]])

    assert mock_instance.iter_compromised_credentials.call_args.kwargs["start"] == created.isoformat()


def test_cursor_not_advanced_when_push_fails(atp_connector: UstaAtpConnector, data_storage: Path) -> None:
    atp_connector.push_events_to_intakes.side_effect = RuntimeError("intake unavailable")
    created = datetime.now(UTC) - timedelta(minutes=10)

    with (
        patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client,
        patch("time.sleep"),
    ):
        mock_usta_client.return_value.iter_compromised_credentials.return_value = [
            {"id": 1, "created": created.isoformat()}
        ]
        with pytest.raises(RuntimeError):
            atp_connector.run()

    assert _read_checkpoint(data_storage) is None


def test_boundary_events_are_not_forwarded_twice(atp_connector: UstaAtpConnector) -> None:
    boundary = (datetime.now(UTC) - timedelta(minutes=10)).replace(microsecond=0)
    newer = boundary + timedelta(minutes=1)
    first = [{"id": 1, "created": boundary.isoformat()}, {"id": 2, "created": boundary.isoformat()}]
    # `start` is inclusive: events created at the cursor are returned again, with a late one (id 3)
    second = [*first, {"id": 3, "created": boundary.isoformat()}]
    third = [*first, {"id": 3, "created": boundary.isoformat()}, {"id": 4, "created": newer.isoformat()}]

    mock_instance = _run_until_sleep(atp_connector, [first, second, third])

    starts = [c.kwargs["start"] for c in mock_instance.iter_compromised_credentials.call_args_list]
    assert starts[1:] == [boundary.isoformat(), boundary.isoformat()]
    pushed = [c.kwargs["events"] for c in atp_connector.push_events_to_intakes.call_args_list]
    assert pushed == [
        [json.dumps(e) for e in first],
        [json.dumps({"id": 3, "created": boundary.isoformat()})],
        [json.dumps({"id": 4, "created": newer.isoformat()})],
    ]
    assert atp_connector.cursor.offset == newer


def test_partial_collection_on_api_error(atp_connector: UstaAtpConnector, data_storage: Path) -> None:
    created = (datetime.now(UTC) - timedelta(minutes=10)).replace(microsecond=0)

    def failing_iterator(**_: Any) -> Any:
        yield {"id": 1, "created": created.isoformat()}
        raise UstaAPIError("Server error 502")

    with (
        patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client,
        patch("time.sleep", side_effect=StopTestError),
    ):
        mock_usta_client.return_value.iter_compromised_credentials.side_effect = failing_iterator
        with pytest.raises(StopTestError):
            atp_connector.run()

    atp_connector.push_events_to_intakes.assert_called_once()
    # events are requested in ascending order, so the cursor can move to the last forwarded one
    assert _read_checkpoint(data_storage) == created
