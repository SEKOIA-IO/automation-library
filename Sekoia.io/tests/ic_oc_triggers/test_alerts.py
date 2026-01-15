import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock

from sekoiaio.triggers.alerts import (
    AlertCreatedTrigger,
    SecurityAlertsTrigger,
    AlertUpdatedTrigger,
    AlertStatusChangedTrigger,
    AlertCommentCreatedTrigger,
    AlertEventsThresholdTrigger,
    AlertEventsThresholdConfiguration,
)
from sekoiaio.triggers.helpers.state_manager import AlertStateManager


@pytest.fixture
def alert_trigger(module_configuration, symphony_storage):
    alert_trigger = SecurityAlertsTrigger()
    alert_trigger._data_path = symphony_storage
    alert_trigger.configuration = {}
    alert_trigger.module.configuration = module_configuration
    alert_trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    alert_trigger.log = Mock()

    yield alert_trigger


@pytest.fixture
def sample_sicalertapi_mock(sample_sicalertapi):
    alert_uuid = sample_sicalertapi.get("uuid")
    mock = requests_mock.Mocker()
    mock.get(f"http://fake.url/api/v1/sic/alerts/{alert_uuid}", json=sample_sicalertapi)

    yield mock


def test_securityalertstrigger_init(alert_trigger):
    assert type(alert_trigger) == SecurityAlertsTrigger


def test_securityalertstrigger_handler_dispatch_alert_message(alert_trigger, sample_notifications):
    alert_trigger.handle_event = Mock()

    for message in sample_notifications:
        alert_trigger.handler_dispatcher(json.dumps(message))
        alert_trigger.handle_event.assert_called()


def test_securityalertstrigger_handle_alert_invalid_message(alert_trigger):
    invalid_messages = [
        {"event_version": "1", "event_type": "alert"},
        {"event_version": "1", "event_type": "alert", "attributes": {}},
        {
            "event_version": "1",
            "event_type": "alert",
            "attributes": {"event": "alert-created"},
        },
    ]

    for message in invalid_messages:
        alert_trigger.handler_dispatcher(json.dumps(message))


def test_securityalertstrigger_retrieve_alert_from_api(alert_trigger, sample_notifications, sample_sicalertapi):
    alert_uuid = sample_sicalertapi.get("uuid")

    with requests_mock.Mocker() as mock:
        mock.get(f"http://fake.url/api/v1/sic/alerts/{alert_uuid}", json=sample_sicalertapi)

        alert = alert_trigger._retrieve_alert_from_alertapi(alert_uuid)
        assert sorted(alert) == sorted(sample_sicalertapi)


def test_securityalertstrigger_retrieve_alert_from_api_exp_raised(
    alert_trigger, samplenotif_alert_created, requests_mock
):
    alert_uuid = samplenotif_alert_created["attributes"]["uuid"]
    requests_mock.get(f"http://fake.url/api/v1/sic/alerts/{alert_uuid}", status_code=500)

    with patch("tenacity.nap.time"):
        alert_trigger.handle_event(samplenotif_alert_created)
        alert_trigger.log.assert_called()


def test_securityalertstrigger_retrieve_alert_not_json(alert_trigger, samplenotif_alert_created, requests_mock):
    alert_uuid = samplenotif_alert_created["attributes"]["uuid"]
    requests_mock.get(f"http://fake.url/api/v1/sic/alerts/{alert_uuid}", status_code=200, text="not json")

    with patch("tenacity.nap.time"):
        alert_trigger.handle_event(samplenotif_alert_created)
        alert_trigger.log.assert_called()


def test_securityalertstrigger_handle_alert_send_message(
    alert_trigger,
    sample_notifications,
    sample_sicalertapi_mock,
    sample_sicalertapi,
):
    alert_trigger.send_event = MagicMock()

    with sample_sicalertapi_mock:
        notification = sample_notifications[0]
        alert_trigger.handle_event(notification)

        # `send_event()` should be called once with defined
        # arguments. We only test a subset of arguments send.
        alert_trigger.send_event.assert_called_once()

        args, kwargs = alert_trigger.send_event.call_args

        for entry in ["directory", "event", "event_name", "remove_directory"]:
            assert kwargs.get(entry) is not None

        evt = kwargs.get("event")
        assert evt.get("file_path") == "alert.json"
        assert evt.get("alert_uuid") == notification.get("attributes").get("uuid")


@pytest.fixture
def alert_created_trigger(module_configuration, symphony_storage):
    trigger = AlertCreatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"

    yield trigger


def test_single_event_triggers(alert_created_trigger, sample_sicalertapi_mock, sample_notifications):
    alert_created_trigger.send_event = MagicMock()

    with sample_sicalertapi_mock:
        # Calling the trigger with an alert created notification should create an event
        alert_created_trigger.handle_event(sample_notifications[0])
        alert_created_trigger.send_event.assert_called_once()

        # All other notification types should not
        for notification in sample_notifications[1:]:
            alert_created_trigger.handle_event(notification)

        alert_created_trigger.send_event.assert_called_once()


def test_single_event_triggers_without_alert_uuid(alert_created_trigger, sample_sicalertapi_mock):
    alert_created_trigger.send_event = MagicMock()
    notification_without_alert_uuid = {
        "metadata": {
            "version": 2,
            "uuid": "a8fb31cb-7310-4f59-afc2-d52033b5cf78",
            "created_at": "2019-09-06T07:32:03.256679+00:00",
            "community_uuid": "cc93fe3f-c26b-4eb1-82f7-082209cf1892",
        },
        "type": "alert",
        "action": "created",
        "attributes": {
            "short_id": "ALakbd8NXp9W",
        },
    }
    with sample_sicalertapi_mock:
        # Calling the trigger with an alert created notification should create an event
        alert_created_trigger.handle_event(notification_without_alert_uuid)
        alert_created_trigger.send_event.assert_not_called()


def test_single_event_triggers_updated(
    alert_created_trigger,
    sample_sicalertapi_mock,
    module_configuration,
    symphony_storage,
    samplenotif_alert_updated,
    sample_notifications,
):
    trigger = AlertUpdatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.send_event = MagicMock()

    with sample_sicalertapi_mock:
        # Calling the trigger with an alert updated notification should create an event
        trigger.handle_event(samplenotif_alert_updated)
        trigger.send_event.assert_called_once()

        # All other notification types should not
        for notification in sample_notifications:
            if not (notification["action"] == "updated" and notification["type"] == "alert"):
                trigger.handle_event(notification)

        trigger.send_event.assert_called_once()


def test_single_event_triggers_status_changed(
    alert_created_trigger,
    sample_sicalertapi_mock,
    module_configuration,
    symphony_storage,
    samplenotif_alert_status_changed,
    sample_notifications,
):
    trigger = AlertStatusChangedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.send_event = MagicMock()

    with sample_sicalertapi_mock:
        # Calling the trigger with an alert statuschanged notification should create an event
        trigger.handle_event(samplenotif_alert_status_changed)
        trigger.send_event.assert_called_once()

        # All other notification types should not
        for notification in sample_notifications:
            if notification != samplenotif_alert_status_changed:
                trigger.handle_event(notification)

        trigger.send_event.assert_called_once()


def test_single_event_triggers_comments_added(
    alert_created_trigger,
    sample_sicalertapi,
    module_configuration,
    symphony_storage,
    samplenotif_alert_comment_created,
    sample_notifications,
):
    trigger = AlertCommentCreatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.send_event = MagicMock()

    alert_uuid = samplenotif_alert_comment_created.get("attributes").get("alert_uuid")
    comment_uuid = samplenotif_alert_comment_created.get("attributes").get("uuid")

    with requests_mock.Mocker() as mock:
        mock.get(f"http://fake.url/api/v1/sic/alerts/{alert_uuid}", json=sample_sicalertapi)

        mock.get(
            f"http://fake.url/api/v1/sic/alerts/{alert_uuid}/comments/{comment_uuid}",
            json={
                "uuid": "095be615-a8ad-4c33-8e9c-c7612fbf6c9f",
                "content": "string",
                "author": "string",
                "date": 0,
                "created_by": "string",
                "created_by_type": "string",
                "unseen": True,
            },
        )
        # Calling the trigger with an alert commentadded notification should create an event
        trigger.handle_event(samplenotif_alert_comment_created)
        trigger.send_event.assert_called_once()

        # All other notification types should not
        for notification in sample_notifications:
            if notification != samplenotif_alert_comment_created:
                trigger.handle_event(notification)

        trigger.send_event.assert_called_once()


def test_invalid_events_dont_triggers_comments_added(
    module_configuration,
    symphony_storage,
    sample_sicalertapi,
    samplenotif_alert_comment_created,
):
    trigger = AlertCommentCreatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.send_event = MagicMock()
    trigger.log = Mock()

    invalid_notification = {
        "metadata": {
            "version": 2,
            "community_uuid": "6ffbe55b-d30a-4dc4-bc52-a213dce0af29",
            "uuid": "94ef1f9d-ebad-42ba-98d7-2be3447c6bd0",
            "created_at": "2019-09-06T07:07:54.830677+00:00",
        },
        "type": "alert-comment",
        "action": "created",
        "attributes": {
            "content": "comment",
            "created_by": "c110d686-0b45-4ae7-b917-f15486d0f8c7",
            "created_by_type": "user",
            "alert_short_id": "ALakbd8NXp9W",
        },
    }
    # Calling the trigger with an alert comment missing alert_uuid should not create an event
    trigger.handle_event(invalid_notification)
    trigger.send_event.assert_not_called()
    invalid_notification["attributes"]["alert_uuid"] = "5869b4d8-e3bb-4465-baad-95daf28267c7"
    # Calling the trigger with  alert comment uuid missing comment_uuid should not create an event
    trigger.handle_event(invalid_notification)
    trigger.send_event.assert_not_called()

    # now calling the trigger with a valid notification but with a 404 response from the API
    with requests_mock.Mocker() as mock, patch("tenacity.nap.time"):
        mock.get("http://fake.url/api/v1/sic/alerts/5869b4d8-e3bb-4465-baad-95daf28267c7", json={}, status_code=404)

        trigger.log.assert_not_called()
        invalid_notification["attributes"]["uuid"] = "5869b4d8-e3bb-4465-baad-95daf28267c7"
        trigger.handle_event(invalid_notification)
        trigger.log.assert_called()
        trigger.log.reset_mock()
        # now making the second api call fail
        mock.get("http://fake.url/api/v1/sic/alerts/5869b4d8-e3bb-4465-baad-95daf28267c7", json=sample_sicalertapi)
        mock.get(
            f"http://fake.url/api/v1/sic/alerts/5869b4d8-e3bb-4465-baad-95daf28267c7/comments/5869b4d8-e3bb-4465-baad-95daf28267c7",
            json={},
            status_code=404,
        )
        trigger.log.assert_not_called()
        trigger.handle_event(invalid_notification)
        trigger.log.assert_called()
        trigger.log.reset_mock()
        # now making the second api call return a non json response
        mock.get("http://fake.url/api/v1/sic/alerts/5869b4d8-e3bb-4465-baad-95daf28267c7", json=sample_sicalertapi)
        mock.get(
            f"http://fake.url/api/v1/sic/alerts/5869b4d8-e3bb-4465-baad-95daf28267c7/comments/5869b4d8-e3bb-4465-baad-95daf28267c7",
            text="not json",
            status_code=404,
        )
        trigger.log.assert_not_called()
        trigger.handle_event(invalid_notification)
        trigger.log.assert_called()
        trigger.log.reset_mock()
        # now making the second api call return a non json response
        mock.get(
            f"http://fake.url/api/v1/sic/alerts/5869b4d8-e3bb-4465-baad-95daf28267c7/comments/5869b4d8-e3bb-4465-baad-95daf28267c7",
            text="not json",
            status_code=200,
        )
        trigger.handle_event(invalid_notification)
        trigger.log.assert_called()


def test_alert_trigger_filter_by_rule(
    alert_trigger, samplenotif_alert_created, sample_sicalertapi_mock, sample_sicalertapi
):
    alert_trigger.send_event = MagicMock()
    with sample_sicalertapi_mock:
        # no match
        alert_trigger.configuration = {"rule_filter": "foo"}
        alert_trigger.handle_event(samplenotif_alert_created)
        assert not alert_trigger.send_event.called

        # match rule name
        alert_trigger.configuration = {"rule_filter": sample_sicalertapi["rule"]["name"]}
        alert_trigger.handle_event(samplenotif_alert_created)
        assert alert_trigger.send_event.called

        alert_trigger.send_event.reset_mock()

        # match rule uuid
        alert_trigger.configuration = {"rule_filter": sample_sicalertapi["rule"]["uuid"]}
        alert_trigger.handle_event(samplenotif_alert_created)
        assert alert_trigger.send_event.called

        alert_trigger.send_event.reset_mock()
        # match rule names in list
        alert_trigger.configuration = {"rule_names_filter": [sample_sicalertapi["rule"]["name"]]}
        alert_trigger.handle_event(samplenotif_alert_created)
        assert alert_trigger.send_event.called


def test_comment_trigger_filter_by_rule(
    alert_created_trigger,
    sample_sicalertapi,
    module_configuration,
    symphony_storage,
    samplenotif_alert_comment_created,
    sample_notifications,
):

    trigger = AlertCommentCreatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.send_event = MagicMock()

    alert_uuid = samplenotif_alert_comment_created.get("attributes").get("alert_uuid")
    comment_uuid = samplenotif_alert_comment_created.get("attributes").get("uuid")

    with requests_mock.Mocker() as mock:
        mock.get(f"http://fake.url/api/v1/sic/alerts/{alert_uuid}", json=sample_sicalertapi)

        mock.get(
            f"http://fake.url/api/v1/sic/alerts/{alert_uuid}/comments/{comment_uuid}",
            json={
                "uuid": "095be615-a8ad-4c33-8e9c-c7612fbf6c9f",
                "content": "string",
                "author": "string",
                "date": 0,
                "created_by": "string",
                "created_by_type": "string",
                "unseen": True,
            },
        )

        trigger.configuration = {"rule_filter": "test"}
        trigger.handle_event(samplenotif_alert_comment_created)
        trigger.send_event.assert_not_called()

        trigger.configuration = {"rule_filter": sample_sicalertapi["rule"]["uuid"]}
        trigger.handle_event(samplenotif_alert_comment_created)
        trigger.send_event.assert_called_once()


def test_comment_trigger_filter_notification_function(
    alert_created_trigger,
    sample_sicalertapi,
    module_configuration,
    symphony_storage,
    samplenotif_alert_comment_created,
    sample_notifications,
):

    trigger = AlertCommentCreatedTrigger()
    trigger.configuration = {}
    trigger._data_path = symphony_storage
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.send_event = MagicMock()
    # mock the filter function to return false
    trigger._filter_notifications = MagicMock()
    trigger._filter_notifications.return_value = False

    trigger.handle_event(samplenotif_alert_comment_created)
    trigger.send_event.assert_not_called()


# ==============================================================================
# AlertEventsThresholdTrigger Tests
# ==============================================================================


@pytest.fixture
def threshold_trigger(module_configuration, symphony_storage):
    """Create an AlertEventsThresholdTrigger for testing."""
    trigger = AlertEventsThresholdTrigger()
    trigger._data_path = symphony_storage
    trigger.configuration = {
        "event_count_threshold": 100,
        "time_window_hours": 1,
        "enable_volume_threshold": True,
        "enable_time_threshold": True,
        "check_interval_seconds": 60,
        "state_cleanup_days": 30,
        "fetch_events": False,
        "fetch_all_events": False,
        "max_events_per_fetch": 1000,
    }
    trigger.module.configuration = module_configuration
    trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.send_event = MagicMock()

    return trigger


@pytest.fixture
def sample_threshold_alert():
    """Create a sample alert for threshold testing."""
    return {
        "uuid": "alert-uuid-threshold-1234",
        "short_id": "ALT-12345",
        "events_count": 150,
        "status": {
            "name": "Ongoing",
            "uuid": "status-uuid",
        },
        "rule": {
            "uuid": "rule-uuid-abcd",
            "name": "Suspicious PowerShell Activity",
        },
        "urgency": {
            "current_value": 70,
        },
        "entity": {
            "uuid": "entity-uuid",
            "name": "Test Entity",
        },
        "alert_type": {
            "value": "malware",
        },
        "created_at": "2025-11-14T08:00:00.000000Z",
        "updated_at": "2025-11-14T10:30:00.000000Z",
        "first_seen_at": "2025-11-14T08:00:00.000000Z",
        "last_seen_at": "2025-11-14T10:30:00.000000Z",
    }


class TestAlertEventsThresholdConfiguration:
    """Test AlertEventsThresholdConfiguration validation."""

    def test_valid_configuration(self):
        """Test that valid configuration is accepted."""
        config = AlertEventsThresholdConfiguration(
            event_count_threshold=100,
            time_window_hours=1,
            enable_volume_threshold=True,
            enable_time_threshold=True,
        )
        assert config.event_count_threshold == 100
        assert config.time_window_hours == 1

    def test_at_least_one_threshold_required(self):
        """Test that at least one threshold must be enabled."""
        with pytest.raises(ValueError, match="At least one threshold must be enabled"):
            AlertEventsThresholdConfiguration(
                enable_volume_threshold=False,
                enable_time_threshold=False,
            )

    def test_cannot_use_both_filters(self):
        """Test that both rule filters cannot be used simultaneously."""
        with pytest.raises(ValueError, match="Use either rule_filter OR rule_names_filter"):
            AlertEventsThresholdConfiguration(
                rule_filter="Test Rule",
                rule_names_filter=["Rule 1", "Rule 2"],
            )


class TestAlertEventsThresholdTrigger:
    """Test AlertEventsThresholdTrigger logic."""

    def test_threshold_trigger_init(self, threshold_trigger):
        """Test trigger initialization."""
        assert type(threshold_trigger) == AlertEventsThresholdTrigger
        assert threshold_trigger.configuration["event_count_threshold"] == 100

    def test_first_occurrence_triggers_immediately(self, threshold_trigger, sample_threshold_alert):
        """Test that first occurrence of an alert triggers immediately."""
        threshold_trigger._ensure_initialized()

        # Pass event_count_from_notification (simulating Kafka notification)
        should_trigger, context = threshold_trigger._evaluate_thresholds(
            sample_threshold_alert, previous_state=None, event_count_from_notification=150
        )

        assert should_trigger is True
        assert context["reason"] == "first_occurrence"
        assert context["new_events"] == 150
        assert context["previous_count"] == 0

    def test_volume_threshold_triggers(self, threshold_trigger, sample_threshold_alert):
        """Test that volume threshold triggers correctly."""
        threshold_trigger._ensure_initialized()

        previous_state = {
            "last_triggered_event_count": 50,
            "version": 1,
        }

        with patch.object(threshold_trigger, "_count_events_in_time_window", return_value=0):
            # Pass event_count_from_notification=150 (100 new events since previous 50)
            should_trigger, context = threshold_trigger._evaluate_thresholds(
                sample_threshold_alert, previous_state, event_count_from_notification=150
            )

        assert should_trigger is True
        assert "volume_threshold" in context["reason"]
        assert context["new_events"] == 100

    def test_below_threshold_does_not_trigger(self, threshold_trigger, sample_threshold_alert):
        """Test that alerts below threshold do not trigger."""
        threshold_trigger.configuration["enable_time_threshold"] = False
        threshold_trigger._ensure_initialized()

        previous_state = {
            "last_triggered_event_count": 100,
            "version": 1,
        }

        # Pass event_count_from_notification=150 (only 50 new events, below 100 threshold)
        should_trigger, context = threshold_trigger._evaluate_thresholds(
            sample_threshold_alert, previous_state, event_count_from_notification=150
        )

        assert should_trigger is False
        assert context["reason"] == "no_threshold_met"

    def test_no_new_events_does_not_trigger(self, threshold_trigger, sample_threshold_alert):
        """Test that alerts with no new events do not trigger."""
        threshold_trigger._ensure_initialized()

        previous_state = {
            "last_triggered_event_count": 150,
            "version": 1,
        }

        # Pass event_count_from_notification=150 (same as previous, no new events)
        should_trigger, context = threshold_trigger._evaluate_thresholds(
            sample_threshold_alert, previous_state, event_count_from_notification=150
        )

        assert should_trigger is False
        assert context["reason"] == "no_new_events"

    def test_rule_filter_matches_name(self, threshold_trigger, sample_threshold_alert):
        """Test that rule filter matches by name."""
        threshold_trigger.configuration["rule_filter"] = "Suspicious PowerShell Activity"

        matches = threshold_trigger._should_process_alert(sample_threshold_alert)
        assert matches is True

    def test_rule_filter_matches_uuid(self, threshold_trigger, sample_threshold_alert):
        """Test that rule filter matches by UUID."""
        threshold_trigger.configuration["rule_filter"] = "rule-uuid-abcd"

        matches = threshold_trigger._should_process_alert(sample_threshold_alert)
        assert matches is True

    def test_rule_filter_blocks_non_matching(self, threshold_trigger, sample_threshold_alert):
        """Test that rule filter blocks non-matching alerts."""
        threshold_trigger.configuration["rule_filter"] = "Different Rule Name"

        matches = threshold_trigger._should_process_alert(sample_threshold_alert)
        assert matches is False

    def test_handle_event_with_mocked_api(self, threshold_trigger, sample_threshold_alert):
        """Test the full event handling flow."""
        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {
                "uuid": "alert-uuid-threshold-1234",
            },
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=sample_threshold_alert):
            with patch.object(threshold_trigger, "_count_events_in_time_window", return_value=10):
                threshold_trigger.handle_event(message)

                # First occurrence should trigger
                assert threshold_trigger.send_event.called


class TestAlertLockManagement:
    """Test alert lock management functionality."""

    def test_get_alert_lock_creates_new_lock(self, threshold_trigger):
        """Test that getting a lock for a new alert creates it."""
        threshold_trigger._ensure_initialized()

        lock = threshold_trigger._get_alert_lock("alert-1")
        assert lock is not None
        assert "alert-1" in threshold_trigger._alert_locks

    def test_get_alert_lock_returns_same_lock(self, threshold_trigger):
        """Test that getting the same lock twice returns the same object."""
        threshold_trigger._ensure_initialized()

        lock1 = threshold_trigger._get_alert_lock("alert-1")
        lock2 = threshold_trigger._get_alert_lock("alert-1")
        assert lock1 is lock2

    def test_alert_locks_bounded_cache(self, threshold_trigger):
        """Test that alert locks cache is bounded to max_locks."""
        threshold_trigger._ensure_initialized()
        threshold_trigger._max_locks = 10

        # Create 20 locks
        for i in range(20):
            threshold_trigger._get_alert_lock(f"alert-{i}")

        # Cache should be pruned to stay under max_locks
        assert len(threshold_trigger._alert_locks) <= 10

    def test_alert_locks_prunes_unlocked_entries(self, threshold_trigger):
        """Test that cache pruning removes only unlocked entries."""
        threshold_trigger._ensure_initialized()
        threshold_trigger._max_locks = 5

        # Create and acquire some locks
        locks = []
        for i in range(3):
            lock = threshold_trigger._get_alert_lock(f"alert-{i}")
            lock.acquire()
            locks.append(lock)

        # Create unlocked locks to exceed max
        for i in range(3, 10):
            threshold_trigger._get_alert_lock(f"alert-{i}")

        # Locked entries should remain
        for i in range(3):
            assert f"alert-{i}" in threshold_trigger._alert_locks

        # Release locks
        for lock in locks:
            lock.release()

    def test_alert_locks_logs_warning_at_capacity(self, threshold_trigger):
        """Test that a warning is logged when cache is at capacity."""
        threshold_trigger._ensure_initialized()
        threshold_trigger._max_locks = 5

        # Create and acquire all locks to prevent pruning
        locks = []
        for i in range(5):
            lock = threshold_trigger._get_alert_lock(f"alert-{i}")
            lock.acquire()
            locks.append(lock)

        # Try to add one more
        threshold_trigger._get_alert_lock("alert-extra")

        # Check warning was logged
        assert any("Alert locks cache at capacity" in str(call) for call in threshold_trigger.log.call_args_list)

        # Release locks
        for lock in locks:
            lock.release()


@pytest.fixture
def mock_logger():
    """Mock logger function for tests."""
    return Mock()


@pytest.fixture
def state_file_path(tmp_path):
    """Temporary state file path for tests."""
    return tmp_path / "test_state.json"


@pytest.fixture
def state_manager(state_file_path, mock_logger):
    """Create AlertStateManager instance for tests."""
    return AlertStateManager(state_file_path, logger=mock_logger)


class TestAlertStateManager:
    def test_init_creates_empty_state(self, state_manager):
        """Test that initialization creates empty state structure."""
        assert "alerts" in state_manager._state
        assert "metadata" in state_manager._state
        assert state_manager._state["metadata"]["version"] == "1.1"
        assert len(state_manager._state["alerts"]) == 0

    def test_load_state_from_nonexistent_file(self, state_file_path, mock_logger):
        """Test loading state when file doesn't exist."""
        manager = AlertStateManager(state_file_path, logger=mock_logger)

        assert manager._state["alerts"] == {}
        assert manager._state["metadata"]["version"] == "1.1"

    def test_load_state_with_corrupted_json(self, state_file_path, mock_logger):
        """Test loading state with corrupted JSON file."""
        # Create a corrupted JSON file
        state_file_path.write_text("{invalid json")

        manager = AlertStateManager(state_file_path, logger=mock_logger)

        # Should start with fresh state
        assert manager._state["alerts"] == {}
        assert manager._state["metadata"]["version"] == "1.1"
        # Should log error
        mock_logger.assert_called()

    def test_get_alert_state_existing(self, state_manager):
        """Test getting state for existing alert."""
        alert_uuid = "test-alert-123"
        state_manager._state["alerts"][alert_uuid] = {
            "alert_uuid": alert_uuid,
            "alert_short_id": "AL123",
            "last_triggered_event_count": 10,
            "total_triggers": 2,
        }

        result = state_manager.get_alert_state(alert_uuid)

        assert result is not None
        assert result["alert_uuid"] == alert_uuid
        assert result["last_triggered_event_count"] == 10

    def test_get_alert_state_nonexistent(self, state_manager):
        """Test getting state for non-existent alert."""
        result = state_manager.get_alert_state("nonexistent-uuid")
        assert result is None

    def test_update_alert_state_new_alert(self, state_manager):
        """Test updating state for a new alert."""
        alert_uuid = "new-alert-456"
        alert_short_id = "AL456"
        rule_uuid = "rule-789"
        rule_name = "Test Rule"
        event_count = 5

        state_manager.update_alert_state(
            alert_uuid=alert_uuid,
            alert_short_id=alert_short_id,
            rule_uuid=rule_uuid,
            rule_name=rule_name,
            event_count=event_count,
        )

        state = state_manager.get_alert_state(alert_uuid)
        assert state is not None
        assert state["alert_uuid"] == alert_uuid
        assert state["alert_short_id"] == alert_short_id
        assert state["rule_uuid"] == rule_uuid
        assert state["rule_name"] == rule_name
        assert state["last_triggered_event_count"] == event_count
        assert state["total_triggers"] == 1
        assert state["version"] == 1

    def test_update_alert_state_existing_alert(self, state_manager):
        """Test updating state for an existing alert."""
        alert_uuid = "existing-alert-789"
        alert_short_id = "AL789"

        # Create initial state
        state_manager.update_alert_state(
            alert_uuid=alert_uuid,
            alert_short_id=alert_short_id,
            rule_uuid="rule-1",
            rule_name="Rule 1",
            event_count=5,
        )

        # Update state
        state_manager.update_alert_state(
            alert_uuid=alert_uuid,
            alert_short_id=alert_short_id,
            rule_uuid="rule-1",
            rule_name="Rule 1",
            event_count=15,
        )

        state = state_manager.get_alert_state(alert_uuid)
        assert state["last_triggered_event_count"] == 15
        assert state["total_triggers"] == 2
        assert state["version"] == 2

    def test_cleanup_old_states_removes_old_alerts(self, state_manager):
        """Test cleanup removes alerts older than cutoff date."""
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=35)

        # Add old alert using update_alert_state to ensure it's persisted
        state_manager._state["alerts"]["old-alert"] = {
            "alert_uuid": "old-alert",
            "alert_short_id": "AL_OLD",
            "last_triggered_at": old_date.isoformat(),
        }
        state_manager._save_state()

        # Add recent alert
        state_manager._state["alerts"]["recent-alert"] = {
            "alert_uuid": "recent-alert",
            "alert_short_id": "AL_RECENT",
            "last_triggered_at": now.isoformat(),
        }
        state_manager._save_state()

        cutoff_date = now - timedelta(days=30)
        removed = state_manager.cleanup_old_states(cutoff_date)

        assert removed == 1
        assert "old-alert" not in state_manager._state["alerts"]
        assert "recent-alert" in state_manager._state["alerts"]

    def test_cleanup_old_states_no_old_alerts(self, state_manager):
        """Test cleanup when there are no old alerts."""
        now = datetime.now(timezone.utc)

        # Add only recent alert using update_alert_state to ensure it's persisted
        state_manager._state["alerts"]["recent-alert"] = {
            "alert_uuid": "recent-alert",
            "alert_short_id": "AL_RECENT",
            "last_triggered_at": now.isoformat(),
        }
        state_manager._save_state()

        cutoff_date = now - timedelta(days=30)
        removed = state_manager.cleanup_old_states(cutoff_date)

        assert removed == 0
        assert "recent-alert" in state_manager._state["alerts"]

    def test_get_stats(self, state_manager):
        """Test getting statistics."""
        # Add some alerts
        state_manager._state["alerts"]["alert1"] = {"alert_uuid": "alert1"}
        state_manager._state["alerts"]["alert2"] = {"alert_uuid": "alert2"}
        state_manager._state["alerts"]["alert3"] = {"alert_uuid": "alert3"}

        stats = state_manager.get_stats()

        assert stats["total_alerts"] == 3
        assert stats["version"] == "1.1"
        assert "last_cleanup" in stats

    def test_save_and_load_state_persistence(self, state_file_path, mock_logger):
        """Test that state persists across manager instances."""
        # Create first manager and add state
        manager1 = AlertStateManager(state_file_path, logger=mock_logger)
        manager1.update_alert_state(
            alert_uuid="persist-test",
            alert_short_id="AL_PERSIST",
            rule_uuid="rule-persist",
            rule_name="Persist Rule",
            event_count=42,
        )

        # Create second manager with same file
        manager2 = AlertStateManager(state_file_path, logger=mock_logger)

        # Verify state was loaded
        state = manager2.get_alert_state("persist-test")
        assert state is not None
        assert state["alert_short_id"] == "AL_PERSIST"
        assert state["last_triggered_event_count"] == 42

    def test_logger_failure_silently_handled(self, state_file_path):
        """Test that logger failures don't crash the manager."""
        failing_logger = Mock(side_effect=Exception("Logger failed"))

        # Should not raise exception despite logger failure
        manager = AlertStateManager(state_file_path, logger=failing_logger)

        # Operations should still work
        manager.update_alert_state(
            alert_uuid="test",
            alert_short_id="AL_TEST",
            rule_uuid="rule",
            rule_name="Rule",
            event_count=1,
        )

        state = manager.get_alert_state("test")
        assert state is not None

    def test_migrate_state_maintains_structure(self, state_manager):
        """Test that state migration maintains required structure."""
        old_state = {"alerts": {"old": {}}}

        migrated = state_manager._migrate_state(old_state)

        assert "alerts" in migrated
        assert "metadata" in migrated
        assert migrated["metadata"]["version"] == "1.1"

    def test_update_alert_state_with_ioerror(self, state_file_path, mock_logger):
        """Test handling of IOError during state update."""
        manager = AlertStateManager(state_file_path, logger=mock_logger)

        # Mock Path.open to raise IOError on write
        with patch.object(Path, "open", side_effect=IOError("Disk full")):
            with pytest.raises(IOError):
                manager.update_alert_state(
                    alert_uuid="test",
                    alert_short_id="AL_TEST",
                    rule_uuid="rule",
                    rule_name="Rule",
                    event_count=1,
                )

            # Verify error was logged
            assert mock_logger.called
            # Check that logger was called with error level and appropriate message
            log_calls = [str(call) for call in mock_logger.call_args_list]
            assert any("error" in call.lower() or "failed" in call.lower() for call in log_calls)

    def test_cleanup_with_exception_propagates(self, state_manager):
        """Test that exceptions during cleanup are propagated."""
        # Mock _load_state to raise exception
        with patch.object(state_manager, "_load_state", side_effect=Exception("Load failed")):
            with pytest.raises(Exception, match="Load failed"):
                state_manager.cleanup_old_states(datetime.now(timezone.utc))


# ==============================================================================
# AlertEventsThresholdTrigger - Event Fetching Tests
# ==============================================================================


@pytest.fixture
def sample_events():
    """Sample events data for testing."""
    return [
        {
            "uuid": "event-uuid-1",
            "created_at": "2025-11-14T08:00:00.000000Z",
            "event_type": "process-creation",
            "alert": {"uuid": "alert-uuid-threshold-1234", "short_id": "ALT-12345"},
        },
        {
            "uuid": "event-uuid-2",
            "created_at": "2025-11-14T09:00:00.000000Z",
            "event_type": "network-connection",
            "alert": {"uuid": "alert-uuid-threshold-1234", "short_id": "ALT-12345"},
        },
        {
            "uuid": "event-uuid-3",
            "created_at": "2025-11-14T10:00:00.000000Z",
            "event_type": "file-modification",
            "alert": {"uuid": "alert-uuid-threshold-1234", "short_id": "ALT-12345"},
        },
    ]


class TestAlertEventsThresholdConfiguration_EventFetching:
    """Test event fetching configuration parameters."""

    def test_fetch_events_default_false(self):
        """Test that fetch_events defaults to False."""
        config = AlertEventsThresholdConfiguration()
        assert config.fetch_events is False

    def test_fetch_all_events_default_false(self):
        """Test that fetch_all_events defaults to False."""
        config = AlertEventsThresholdConfiguration()
        assert config.fetch_all_events is False

    def test_max_events_per_fetch_default(self):
        """Test that max_events_per_fetch has correct default."""
        config = AlertEventsThresholdConfiguration()
        assert config.max_events_per_fetch == 1000

    def test_max_events_per_fetch_validation(self):
        """Test that max_events_per_fetch is validated."""
        # Valid values
        config = AlertEventsThresholdConfiguration(max_events_per_fetch=500)
        assert config.max_events_per_fetch == 500

        # Should accept max value
        config = AlertEventsThresholdConfiguration(max_events_per_fetch=10000)
        assert config.max_events_per_fetch == 10000

        # Should fail below min
        with pytest.raises(ValueError):
            AlertEventsThresholdConfiguration(max_events_per_fetch=0)

        # Should fail above max
        with pytest.raises(ValueError):
            AlertEventsThresholdConfiguration(max_events_per_fetch=10001)


class TestAlertEventsThresholdTrigger_EventFetching:
    """Test event fetching functionality."""

    def test_trigger_event_search_job_success(self, threshold_trigger, sample_threshold_alert, requests_mock):
        """Test successful event search job triggering."""
        threshold_trigger._ensure_initialized()

        job_uuid = "job-uuid-12345"

        requests_mock.post(
            "http://fake.url/api/v1/sic/conf/events/search/jobs",
            json={"uuid": job_uuid},
            status_code=200,
        )

        result = threshold_trigger._trigger_event_search_job(
            alert_short_id="ALT-12345",
            earliest_time="2025-11-14T08:00:00.000000Z",
            latest_time="2025-11-14T10:30:00.000000Z",
            limit=1000,
        )

        assert result == job_uuid
        assert requests_mock.call_count == 1

        # Verify request payload
        request = requests_mock.request_history[0]
        payload = request.json()
        assert payload["term"] == 'alert_short_ids:"ALT-12345"'
        assert payload["earliest_time"] == "2025-11-14T08:00:00.000000Z"
        assert payload["latest_time"] == "2025-11-14T10:30:00.000000Z"
        assert payload["max_last_events"] == 1000
        assert payload["visible"] is False

    def test_trigger_event_search_job_failure(self, threshold_trigger, requests_mock):
        """Test event search job triggering failure."""
        threshold_trigger._ensure_initialized()

        requests_mock.post(
            "http://fake.url/api/v1/sic/conf/events/search/jobs",
            status_code=500,
            json={"error": "Internal server error"},
        )

        with patch("tenacity.nap.time"):
            result = threshold_trigger._trigger_event_search_job(
                alert_short_id="ALT-12345",
                earliest_time="2025-11-14T08:00:00.000000Z",
                latest_time="2025-11-14T10:30:00.000000Z",
                limit=1000,
            )

        assert result is None
        assert threshold_trigger.log_exception.called

    def test_wait_for_search_job_success(self, threshold_trigger, requests_mock):
        """Test waiting for search job completion."""
        threshold_trigger._ensure_initialized()

        job_uuid = "job-uuid-12345"

        # First call: status 0 (not started)
        # Second call: status 1 (in progress)
        # Third call: status 2 (completed)
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}",
            [
                {"json": {"status": 0}},
                {"json": {"status": 1}},
                {"json": {"status": 2}},
            ],
        )

        result = threshold_trigger._wait_for_search_job(job_uuid, timeout=10)

        assert result is True

    def test_wait_for_search_job_timeout(self, threshold_trigger, requests_mock):
        """Test search job timeout."""
        threshold_trigger._ensure_initialized()

        job_uuid = "job-uuid-12345"

        # Always return status 0 (not started)
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}",
            json={"status": 0},
        )

        with patch("time.time", side_effect=[0, 1, 2, 400]):  # Simulate timeout
            result = threshold_trigger._wait_for_search_job(job_uuid, timeout=10)

        assert result is False

    def test_get_search_job_results_success(self, threshold_trigger, sample_events, requests_mock):
        """Test retrieving search job results."""
        threshold_trigger._ensure_initialized()

        job_uuid = "job-uuid-12345"

        # Single page results (limit=100 gets all 3 events in one page)
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}/events",
            json={"items": sample_events, "total": 3},
        )

        results = threshold_trigger._get_search_job_results(job_uuid, limit=100)

        assert results is not None
        assert len(results) == 3

    def test_get_search_job_results_empty(self, threshold_trigger, requests_mock):
        """Test retrieving empty search job results."""
        threshold_trigger._ensure_initialized()

        job_uuid = "job-uuid-12345"

        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}/events",
            json={"items": [], "total": 0},
        )

        results = threshold_trigger._get_search_job_results(job_uuid, limit=100)

        assert results is not None
        assert len(results) == 0

    def test_get_search_job_results_pagination(self, threshold_trigger, requests_mock):
        """Test retrieving search job results with multiple pages."""
        threshold_trigger._ensure_initialized()

        job_uuid = "job-uuid-12345"

        # Create 250 events to test multi-page retrieval with page_size=100
        page1_events = [{"uuid": f"event-{i}", "data": f"page1-{i}"} for i in range(100)]
        page2_events = [{"uuid": f"event-{i}", "data": f"page2-{i}"} for i in range(100, 200)]
        page3_events = [{"uuid": f"event-{i}", "data": f"page3-{i}"} for i in range(200, 250)]

        # Mock paginated responses
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}/events",
            [
                {"json": {"items": page1_events, "total": 250}},
                {"json": {"items": page2_events, "total": 250}},
                {"json": {"items": page3_events, "total": 250}},
            ],
        )

        results = threshold_trigger._get_search_job_results(job_uuid, limit=100)

        assert results is not None
        assert len(results) == 250
        assert results[0]["uuid"] == "event-0"
        assert results[99]["uuid"] == "event-99"
        assert results[100]["uuid"] == "event-100"
        assert results[249]["uuid"] == "event-249"

        # Verify pagination was done correctly
        assert requests_mock.call_count == 3
        assert requests_mock.request_history[0].qs == {"limit": ["100"], "offset": ["0"]}
        assert requests_mock.request_history[1].qs == {"limit": ["100"], "offset": ["100"]}
        assert requests_mock.request_history[2].qs == {"limit": ["100"], "offset": ["200"]}

    def test_fetch_alert_events_all_events(
        self, threshold_trigger, sample_threshold_alert, sample_events, requests_mock
    ):
        """Test fetching all events from an alert."""
        threshold_trigger._ensure_initialized()

        job_uuid = "job-uuid-12345"

        # Mock search job creation
        requests_mock.post(
            "http://fake.url/api/v1/sic/conf/events/search/jobs",
            json={"uuid": job_uuid},
        )

        # Mock job status
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}",
            [{"json": {"status": 1}}, {"json": {"status": 2}}],
        )

        # Mock results
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}/events",
            json={"items": sample_events, "total": 3},
        )

        events = threshold_trigger._fetch_alert_events(
            alert=sample_threshold_alert,
            fetch_all=True,
            previous_state=None,
            max_events=1000,
        )

        assert events is not None
        assert len(events) == 3

        # Verify the search job was created with correct time range
        job_request = requests_mock.request_history[0]
        payload = job_request.json()
        assert payload["earliest_time"] == sample_threshold_alert["first_seen_at"]
        assert payload["latest_time"] == sample_threshold_alert["last_seen_at"]

    def test_fetch_alert_events_new_only(
        self, threshold_trigger, sample_threshold_alert, sample_events, requests_mock
    ):
        """Test fetching only new events from an alert."""
        threshold_trigger._ensure_initialized()

        job_uuid = "job-uuid-12345"
        previous_state = {
            "last_triggered_at": "2025-11-14T09:00:00.000000Z",
            "last_triggered_event_count": 100,
        }

        # Mock search job creation
        requests_mock.post(
            "http://fake.url/api/v1/sic/conf/events/search/jobs",
            json={"uuid": job_uuid},
        )

        # Mock job status
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}",
            [{"json": {"status": 1}}, {"json": {"status": 2}}],
        )

        # Mock results
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}/events",
            json={"items": sample_events, "total": 3},
        )

        events = threshold_trigger._fetch_alert_events(
            alert=sample_threshold_alert,
            fetch_all=False,
            previous_state=previous_state,
            max_events=1000,
        )

        assert events is not None
        assert len(events) == 3

        # Verify the search job used last_triggered_at as earliest_time
        job_request = requests_mock.request_history[0]
        payload = job_request.json()
        assert payload["earliest_time"] == previous_state["last_triggered_at"]

    def test_fetch_alert_events_api_failure(self, threshold_trigger, sample_threshold_alert, requests_mock):
        """Test event fetching when API fails."""
        threshold_trigger._ensure_initialized()

        requests_mock.post(
            "http://fake.url/api/v1/sic/conf/events/search/jobs",
            status_code=500,
        )

        with patch("tenacity.nap.time"):
            events = threshold_trigger._fetch_alert_events(
                alert=sample_threshold_alert,
                fetch_all=True,
                previous_state=None,
                max_events=1000,
            )

        assert events is None

    def test_send_threshold_event_with_events(self, threshold_trigger, sample_threshold_alert, sample_events):
        """Test sending threshold event with events included."""
        threshold_trigger._ensure_initialized()

        context = {
            "reason": "volume_threshold",
            "new_events": 100,
            "previous_count": 50,
            "current_count": 150,
        }

        threshold_trigger._send_threshold_event(
            alert=sample_threshold_alert,
            event_type="alert",
            context=context,
            events=sample_events,
            previous_state=None,
        )

        # Verify send_event was called
        assert threshold_trigger.send_event.called

        # Get the event payload
        args, kwargs = threshold_trigger.send_event.call_args
        event = kwargs["event"]

        # Verify events file path is included
        assert "events_file_path" in event
        assert event["events_file_path"] == "events.json"
        assert event["fetched_events_count"] == 3

        # Verify events.json file was created
        directory = kwargs["directory"]
        work_dir = threshold_trigger._data_path / directory
        events_file = work_dir / "events.json"
        assert events_file.exists()

        # Verify events content
        import orjson

        with events_file.open("rb") as f:
            saved_events = orjson.loads(f.read())
        assert len(saved_events) == 3
        assert saved_events[0]["uuid"] == "event-uuid-1"

    def test_send_threshold_event_without_events(self, threshold_trigger, sample_threshold_alert):
        """Test sending threshold event without events."""
        threshold_trigger._ensure_initialized()

        context = {
            "reason": "first_occurrence",
            "new_events": 150,
            "previous_count": 0,
            "current_count": 150,
        }

        threshold_trigger._send_threshold_event(
            alert=sample_threshold_alert,
            event_type="alert",
            context=context,
            events=None,
            previous_state=None,
        )

        # Verify send_event was called
        assert threshold_trigger.send_event.called

        # Get the event payload
        args, kwargs = threshold_trigger.send_event.call_args
        event = kwargs["event"]

        # Verify events file path is NOT included
        assert "events_file_path" not in event
        assert "fetched_events_count" not in event

    def test_handle_event_with_event_fetching(
        self, threshold_trigger, sample_threshold_alert, sample_events, requests_mock
    ):
        """Test full event handling with event fetching enabled."""
        threshold_trigger.configuration["fetch_events"] = True
        threshold_trigger.configuration["fetch_all_events"] = False
        threshold_trigger.configuration["max_events_per_fetch"] = 500

        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {
                "uuid": "alert-uuid-threshold-1234",
            },
        }

        job_uuid = "job-uuid-12345"

        # Mock alert API
        requests_mock.get(
            f"http://fake.url/api/v1/sic/alerts/{sample_threshold_alert['uuid']}",
            json=sample_threshold_alert,
        )

        # Mock events API
        requests_mock.post(
            "http://fake.url/api/v1/sic/conf/events/search/jobs",
            json={"uuid": job_uuid},
        )
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}",
            [{"json": {"status": 1}}, {"json": {"status": 2}}],
        )
        requests_mock.get(
            f"http://fake.url/api/v1/sic/conf/events/search/jobs/{job_uuid}/events",
            json={"items": sample_events, "total": 3},
        )

        threshold_trigger.handle_event(message)

        # Verify send_event was called
        assert threshold_trigger.send_event.called

        # Verify events were fetched
        args, kwargs = threshold_trigger.send_event.call_args
        event = kwargs["event"]
        assert "events_file_path" in event
        assert event["fetched_events_count"] == 3

    def test_handle_event_fetch_events_disabled(self, threshold_trigger, sample_threshold_alert):
        """Test event handling with event fetching disabled."""
        threshold_trigger.configuration["fetch_events"] = False

        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {
                "uuid": "alert-uuid-threshold-1234",
            },
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=sample_threshold_alert):
            with patch.object(threshold_trigger, "_count_events_in_time_window", return_value=10):
                with patch.object(threshold_trigger, "_fetch_alert_events") as mock_fetch:
                    threshold_trigger.handle_event(message)

                    # Verify _fetch_alert_events was NOT called
                    assert not mock_fetch.called

                    # Verify send_event was called (first occurrence)
                    assert threshold_trigger.send_event.called

                    # Verify no events in payload
                    args, kwargs = threshold_trigger.send_event.call_args
                    event = kwargs["event"]
                    assert "events_file_path" not in event

    def test_handle_event_fetch_events_failure_continues(self, threshold_trigger, sample_threshold_alert):
        """Test that event handling continues even if event fetching fails."""
        threshold_trigger.configuration["fetch_events"] = True

        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {
                "uuid": "alert-uuid-threshold-1234",
            },
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=sample_threshold_alert):
            with patch.object(threshold_trigger, "_count_events_in_time_window", return_value=10):
                with patch.object(threshold_trigger, "_fetch_alert_events", return_value=None):
                    threshold_trigger.handle_event(message)

                    # Verify send_event was still called despite fetch failure
                    assert threshold_trigger.send_event.called

                    # Verify warning was logged
                    assert any("Failed to fetch events" in str(call) for call in threshold_trigger.log.call_args_list)

    def test_get_alert_lock_creates_new_lock(self, threshold_trigger):
        """Test that _get_alert_lock creates a new lock for unknown alert."""
        alert_uuid = "new-alert-uuid"

        # Get lock for new alert
        lock1 = threshold_trigger._get_alert_lock(alert_uuid)

        # Verify lock was created
        assert alert_uuid in threshold_trigger._alert_locks
        assert lock1 is threshold_trigger._alert_locks[alert_uuid]

        # Getting the same lock again should return the same instance
        lock2 = threshold_trigger._get_alert_lock(alert_uuid)
        assert lock1 is lock2

    def test_get_alert_lock_bounded_cache(self, threshold_trigger):
        """Test that _get_alert_lock implements bounded cache with cleanup."""
        # Fill cache to max capacity
        for i in range(threshold_trigger._max_locks):
            threshold_trigger._get_alert_lock(f"alert-{i}")

        assert len(threshold_trigger._alert_locks) == threshold_trigger._max_locks

        # Adding one more should trigger cleanup
        threshold_trigger._get_alert_lock("alert-overflow")

        # Cache should still be at or below max capacity
        assert len(threshold_trigger._alert_locks) <= threshold_trigger._max_locks

    def test_get_alert_lock_concurrent_access(self, threshold_trigger):
        """Test that _get_alert_lock is thread-safe."""
        from threading import Thread

        alert_uuid = "concurrent-alert"
        locks_obtained = []

        def get_lock():
            lock = threshold_trigger._get_alert_lock(alert_uuid)
            locks_obtained.append(lock)

        # Create multiple threads trying to get the same lock
        threads = [Thread(target=get_lock) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should have gotten the same lock instance
        assert all(lock is locks_obtained[0] for lock in locks_obtained)

    def test_handle_event_locked_with_lock(self, threshold_trigger, sample_threshold_alert):
        """Test that handle_event acquires lock before processing."""
        alert_uuid = "alert-uuid-locked-test"
        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {"uuid": alert_uuid},
        }

        lock_acquired = False
        original_handle_event_locked = threshold_trigger._handle_event_locked

        def mock_handle_event_locked(*args, **kwargs):
            nonlocal lock_acquired
            # Check if lock is currently held
            alert_lock = threshold_trigger._get_alert_lock(alert_uuid)
            lock_acquired = alert_lock.locked()
            # Call original method
            return original_handle_event_locked(*args, **kwargs)

        threshold_trigger._handle_event_locked = mock_handle_event_locked

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=sample_threshold_alert):
            threshold_trigger.handle_event(message)

        # Verify lock was acquired during processing
        assert lock_acquired

    def test_time_threshold_triggers(self, threshold_trigger, sample_threshold_alert):
        """Test that time-based threshold triggers correctly."""
        threshold_trigger.configuration["enable_time_threshold"] = True
        threshold_trigger.configuration["enable_volume_threshold"] = False
        threshold_trigger.configuration["time_window_hours"] = 1

        # Alert with recent event
        alert_with_recent_event = {
            **sample_threshold_alert,
            "events_count": 5,
        }

        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {"uuid": "alert-uuid-time-test"},
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=alert_with_recent_event):
            with patch.object(threshold_trigger, "_count_events_in_time_window", return_value=3):
                threshold_trigger.handle_event(message)

                # Should trigger because there are events in time window
                assert threshold_trigger.send_event.called

    def test_time_threshold_does_not_trigger_when_no_events_in_window(self, threshold_trigger, sample_threshold_alert):
        """Test that time-based threshold does NOT trigger when no events in time window."""
        # Initialize state manager first
        threshold_trigger._ensure_initialized()

        threshold_trigger.configuration["enable_time_threshold"] = True
        threshold_trigger.configuration["enable_volume_threshold"] = False
        threshold_trigger.configuration["time_window_hours"] = 1

        # Create previous state with lower event count
        alert_uuid = "alert-uuid-no-time-events"
        threshold_trigger.state_manager.update_alert_state(
            alert_uuid=alert_uuid,
            alert_short_id="AL_NO_TIME",
            rule_uuid="rule-123",
            rule_name="Test Rule",
            event_count=5,  # Previous count
        )

        # Alert info
        alert = {
            **sample_threshold_alert,
            "uuid": alert_uuid,
            "short_id": "AL_NO_TIME",
        }

        # Message with event count from Kafka notification (similar=10)
        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {
                "uuid": alert_uuid,
                "updated": {"similar": 10},  # 10 events total, 5 new
            },
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=alert):
            # Mock _count_events_in_time_window to return 0 (no events in time window)
            with patch.object(threshold_trigger, "_count_events_in_time_window", return_value=0):
                threshold_trigger.handle_event(message)

                # Should NOT trigger because no events in time window (even though there are new events)
                assert not threshold_trigger.send_event.called

    def test_state_cleanup_periodic(self, threshold_trigger, sample_threshold_alert):
        """Test that state cleanup runs periodically."""
        # Initialize state manager first
        threshold_trigger._ensure_initialized()

        threshold_trigger.configuration["state_cleanup_days"] = 30
        threshold_trigger._last_cleanup = None  # Force cleanup to run
        threshold_trigger.configuration["enable_volume_threshold"] = True
        threshold_trigger.configuration["event_count_threshold"] = 10

        # Set up alert with events that will trigger
        alert = {
            **sample_threshold_alert,
            "events_count": 15,
        }

        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {"uuid": "alert-cleanup-test"},
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=alert):
            with patch.object(threshold_trigger.state_manager, "cleanup_old_states", return_value=2) as mock_cleanup:
                threshold_trigger.handle_event(message)

                # Verify cleanup was called during handle_event
                assert mock_cleanup.called

    def test_initialization_with_custom_config(self, module_configuration, symphony_storage):
        """Test trigger initialization with custom configuration."""
        trigger = AlertEventsThresholdTrigger()
        trigger._data_path = symphony_storage
        trigger.module.configuration = module_configuration
        trigger.configuration = {
            "enable_volume_threshold": True,
            "enable_time_threshold": True,
            "event_count_threshold": 50,
            "time_window_hours": 2,
            "state_cleanup_days": 60,
        }

        # Trigger initialization
        trigger._ensure_initialized()

        assert trigger._initialized
        assert trigger.state_manager is not None

    def test_evaluate_thresholds_with_previous_state(self, threshold_trigger):
        """Test threshold evaluation with existing previous state."""
        alert = {
            "uuid": "alert-test",
            "short_id": "AL_TEST",
            "rule": {"uuid": "rule-123", "name": "Test Rule"},
        }

        previous_state = {
            "alert_uuid": "alert-test",
            "last_triggered_event_count": 10,
            "total_triggers": 1,
        }

        threshold_trigger.configuration["enable_volume_threshold"] = True
        threshold_trigger.configuration["event_count_threshold"] = 10

        # Pass event_count_from_notification=25 (15 new events since previous 10)
        should_trigger, context = threshold_trigger._evaluate_thresholds(
            alert, previous_state, event_count_from_notification=25
        )

        assert should_trigger
        assert context["reason"] == "volume_threshold"
        assert context["new_events"] == 15
        assert context["previous_count"] == 10
        assert context["current_count"] == 25

    def test_error_handling_api_fetch_failure(self, threshold_trigger):
        """Test error handling when API fetch fails - should log and not send event."""
        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {"uuid": "alert-error-test"},
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", side_effect=Exception("API Error")):
            # Should not raise exception
            threshold_trigger.handle_event(message)

            # Should log the error via log_exception
            assert threshold_trigger.log_exception.called
            # Should NOT send event when API fetch fails
            assert not threshold_trigger.send_event.called

    def test_error_handling_state_update_failure(self, threshold_trigger, sample_threshold_alert):
        """Test error handling when state update fails - should continue and send event."""
        # Initialize state manager first
        threshold_trigger._ensure_initialized()

        threshold_trigger.configuration["enable_volume_threshold"] = True
        threshold_trigger.configuration["event_count_threshold"] = 10

        # Set up alert that should trigger
        alert = {
            **sample_threshold_alert,
            "events_count": 15,
        }

        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {"uuid": "alert-state-error"},
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=alert):
            with patch.object(
                threshold_trigger.state_manager, "update_alert_state", side_effect=Exception("State error")
            ):
                # Should log exception but continue processing (not raise)
                threshold_trigger.handle_event(message)

                # Should log the exception
                assert threshold_trigger.log_exception.called
                # Event should still be sent despite state update failure
                assert threshold_trigger.send_event.called

    def test_error_handling_cleanup_failure(self, threshold_trigger, sample_threshold_alert):
        """Test error handling when cleanup fails - should continue and send event."""
        # Initialize state manager first
        threshold_trigger._ensure_initialized()

        threshold_trigger._last_cleanup = None
        threshold_trigger.configuration["enable_volume_threshold"] = True
        threshold_trigger.configuration["event_count_threshold"] = 10

        # Set up alert that should trigger
        alert = {
            **sample_threshold_alert,
            "events_count": 15,
        }

        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {"uuid": "alert-cleanup-error"},
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=alert):
            with patch.object(
                threshold_trigger.state_manager, "cleanup_old_states", side_effect=Exception("Cleanup error")
            ):
                # Should continue despite cleanup error (not raise)
                threshold_trigger.handle_event(message)

                # Should log the cleanup exception
                assert threshold_trigger.log_exception.called
                # Event should still be sent despite cleanup failure
                assert threshold_trigger.send_event.called

    def test_send_threshold_event_with_context(self, threshold_trigger, sample_threshold_alert):
        """Test that send_threshold_event includes threshold context in event."""
        alert = sample_threshold_alert
        context = {
            "reason": "volume_threshold",
            "new_events": 15,
            "previous_count": 5,
            "current_count": 20,
        }

        threshold_trigger._send_threshold_event(
            alert=alert,
            event_type="alert",
            context=context,
            events=None,
            previous_state=None,
        )

        # Verify send_event was called
        assert threshold_trigger.send_event.called

        # Verify context was included in event (check call args)
        call_args = threshold_trigger.send_event.call_args
        if call_args:
            # Event should be passed as keyword argument
            kwargs = call_args[1] if len(call_args) > 1 else call_args.kwargs
            if "event" in kwargs:
                event = kwargs["event"]
                # Context is added as "trigger_context" in the event
                assert "trigger_context" in event
                assert event["trigger_context"]["reason"] == "volume_threshold"
                assert event["trigger_context"]["new_events"] == 15

    def test_rule_names_filter_blocks_alert(self, threshold_trigger, sample_threshold_alert):
        """Test that rule_names_filter blocks non-matching alerts."""
        threshold_trigger.configuration["rule_names_filter"] = ["Allowed Rule"]
        threshold_trigger.configuration["enable_volume_threshold"] = True
        threshold_trigger.configuration["event_count_threshold"] = 10

        # Alert with different rule name and enough events to trigger
        alert = {
            **sample_threshold_alert,
            "events_count": 15,
            "rule": {"name": "Blocked Rule", "uuid": "rule-123"},
        }

        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {"uuid": "alert-filtered"},
        }

        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi", return_value=alert):
            threshold_trigger.handle_event(message)

            # Verify send_event was not called (filtered out)
            assert not threshold_trigger.send_event.called

    def test_handle_event_missing_uuid(self, threshold_trigger):
        """Test handling of event with missing alert UUID."""
        message = {
            "type": "alert",
            "action": "updated",
            "attributes": {},  # Missing uuid
        }

        threshold_trigger.handle_event(message)

        # Should log warning (verify log was called with message about missing UUID)
        assert threshold_trigger.log.called
        # Check if any call contains a message about missing UUID
        log_calls = [str(call) for call in threshold_trigger.log.call_args_list]
        assert any("uuid" in call.lower() for call in log_calls)
        assert not threshold_trigger.send_event.called

    def test_handle_event_wrong_type(self, threshold_trigger):
        """Test handling of event with wrong type."""
        message = {
            "type": "case",  # Wrong type
            "action": "updated",
            "attributes": {"uuid": "alert-123"},
        }

        threshold_trigger.handle_event(message)

        # Should not proceed
        assert not threshold_trigger.send_event.called

    def test_validated_config_caches_result(self, threshold_trigger):
        """Test that validated_config caches the result."""
        config1 = threshold_trigger.validated_config
        config2 = threshold_trigger.validated_config

        # Should return the same instance
        assert config1 is config2

    def test_initialization_failure_handling(self, module_configuration, symphony_storage):
        """Test handling of initialization failure - should log and raise."""
        trigger = AlertEventsThresholdTrigger()
        trigger._data_path = symphony_storage
        trigger.module.configuration = module_configuration
        trigger.configuration = {
            "enable_volume_threshold": True,
            "event_count_threshold": 10,
        }
        trigger.log_exception = Mock()

        # Mock AlertStateManager to raise exception during initialization
        with patch("sekoiaio.triggers.alerts.AlertStateManager", side_effect=Exception("Initialization error")):
            # Should raise the exception (wrapped or original)
            with pytest.raises(Exception):
                trigger._ensure_initialized()

            # Should have logged the exception
            assert trigger.log_exception.called


# ==============================================================================
# AlertEventsThresholdTrigger - New Optimizations Tests
# ==============================================================================


class TestAlertEventsThresholdTrigger_KafkaNotification:
    """Test using event count from Kafka notifications."""

    def test_event_count_from_kafka_notification_updated(self, threshold_trigger, sample_threshold_alert):
        """Test that event count is extracted from alert:updated notification."""
        threshold_trigger._ensure_initialized()

        # Test _evaluate_thresholds directly with event_count_from_notification
        # This tests that the threshold evaluation uses the count from the notification
        should_trigger, context = threshold_trigger._evaluate_thresholds(
            sample_threshold_alert, previous_state=None, event_count_from_notification=50
        )

        # First occurrence should trigger
        assert should_trigger is True
        assert context["reason"] == "first_occurrence"
        # Verify the context uses the event count from notification (50), not from alert (150)
        assert context["current_count"] == 50
        assert context["new_events"] == 50

    def test_event_count_from_kafka_notification_created(self, threshold_trigger, sample_threshold_alert):
        """Test that event count is extracted from alert:created notification (similar=0)."""
        threshold_trigger._ensure_initialized()

        # Create an alert info as it would be extracted from alert:created notification
        alert_from_created = {
            "uuid": "alert-uuid-created",
            "short_id": "ALT-CREATED",
            "status": {"name": "Pending", "uuid": "status-uuid"},
            "rule": {"uuid": "rule-uuid-abcd", "name": "Test Rule"},
            "entity": {"uuid": "entity-uuid", "name": "Test Entity"},
            "urgency": {"current_value": 50},
            "alert_type": {"category": "malware", "value": "malware"},
        }

        # Test _evaluate_thresholds directly with event_count_from_notification=0
        # This simulates what happens when alert:created notification arrives with similar=0
        should_trigger, context = threshold_trigger._evaluate_thresholds(
            alert_from_created, previous_state=None, event_count_from_notification=0
        )

        # First occurrence should trigger even with 0 events
        assert should_trigger is True
        assert context["reason"] == "first_occurrence"
        assert context["current_count"] == 0
        assert context["new_events"] == 0


class TestAlertEventsThresholdTrigger_AlertInfoOptimization:
    """Test alert info caching to avoid API calls."""

    def test_alert_created_extracts_info_from_notification(self, threshold_trigger):
        """Test that alert:created extracts info directly from notification without API."""
        threshold_trigger._ensure_initialized()

        alert_attrs = {
            "uuid": "alert-uuid-123",
            "short_id": "ALT-123",
            "similar": 0,
            "status_name": "Pending",
            "status_uuid": "status-uuid",
            "urgency_current_value": 70,
            "rule_uuid": "rule-uuid",
            "rule_name": "Test Rule",
            "entity_uuid": "entity-uuid",
            "entity_name": "Test Entity",
            "alert_type_category": "intrusions",
            "alert_type_value": "application-compromise",
            "assets_uuids": ["asset-1", "asset-2"],
        }

        alert = threshold_trigger._extract_alert_from_created_notification(alert_attrs)

        assert alert["uuid"] == "alert-uuid-123"
        assert alert["short_id"] == "ALT-123"
        assert alert["status"]["name"] == "Pending"
        assert alert["rule"]["name"] == "Test Rule"
        assert alert["rule"]["uuid"] == "rule-uuid"
        assert alert["entity"]["name"] == "Test Entity"
        assert len(alert["assets"]) == 2

    def test_get_alert_info_optimized_uses_cache(self, threshold_trigger, sample_threshold_alert):
        """Test that cached alert info is used instead of API call."""
        threshold_trigger._ensure_initialized()

        alert_uuid = "alert-cached-123"

        # Pre-populate the cache directly in state (simulating previous update_alert_info call)
        threshold_trigger.state_manager._state["alerts"][alert_uuid] = {
            "alert_uuid": alert_uuid,
            "alert_short_id": sample_threshold_alert.get("short_id", ""),
            "alert_info": sample_threshold_alert,
            "current_event_count": 10,
        }

        # Should use cache, not API
        with patch.object(threshold_trigger, "_retrieve_alert_from_alertapi") as mock_api:
            alert = threshold_trigger._get_alert_info_optimized(
                alert_uuid=alert_uuid,
                event_action="updated",
                alert_attrs={"uuid": alert_uuid},
            )

            # API should NOT be called
            mock_api.assert_not_called()
            assert alert is not None

    def test_get_alert_info_optimized_falls_back_to_api(self, threshold_trigger, sample_threshold_alert):
        """Test that API is called when cache is empty."""
        threshold_trigger._ensure_initialized()

        alert_uuid = "alert-not-cached-123"

        # Cache is empty, should call API
        with patch.object(
            threshold_trigger, "_retrieve_alert_from_alertapi", return_value=sample_threshold_alert
        ) as mock_api:
            alert = threshold_trigger._get_alert_info_optimized(
                alert_uuid=alert_uuid,
                event_action="updated",
                alert_attrs={"uuid": alert_uuid},
            )

            # API should be called
            mock_api.assert_called_once_with(alert_uuid)
            assert alert is not None


class TestAlertStateManager_NewMethods:
    """Test new AlertStateManager methods for caching and time threshold."""

    def test_update_alert_info_creates_new_entry(self, state_manager):
        """Test that update_alert_info creates a new state entry."""
        alert_uuid = "alert-new-info"
        alert_info = {
            "uuid": alert_uuid,
            "short_id": "ALT-NEW",
            "rule": {"uuid": "rule-uuid", "name": "Test Rule"},
        }

        state_manager.update_alert_info(
            alert_uuid=alert_uuid,
            alert_info=alert_info,
            event_count=5,
        )

        state = state_manager.get_alert_state(alert_uuid)
        assert state is not None
        assert state["alert_uuid"] == alert_uuid
        assert state["current_event_count"] == 5
        assert state["alert_info"] == alert_info
        assert state["last_triggered_event_count"] == 0  # Not triggered yet

    def test_update_alert_info_updates_existing_entry(self, state_manager):
        """Test that update_alert_info updates an existing entry."""
        alert_uuid = "alert-update-info"
        alert_info = {
            "uuid": alert_uuid,
            "short_id": "ALT-UPD",
            "rule": {"uuid": "rule-uuid", "name": "Test Rule"},
        }

        # Create initial entry
        state_manager.update_alert_info(
            alert_uuid=alert_uuid,
            alert_info=alert_info,
            event_count=5,
        )

        # Update with new event count
        state_manager.update_alert_info(
            alert_uuid=alert_uuid,
            alert_info=alert_info,
            event_count=10,
        )

        state = state_manager.get_alert_state(alert_uuid)
        assert state["current_event_count"] == 10
        assert state["last_triggered_event_count"] == 0  # Still not triggered

    def test_get_alert_info_returns_cached_info(self, state_manager):
        """Test that get_alert_info returns cached alert info."""
        alert_uuid = "alert-get-info"
        alert_info = {
            "uuid": alert_uuid,
            "short_id": "ALT-GET",
            "rule": {"uuid": "rule-uuid", "name": "Test Rule"},
        }

        state_manager.update_alert_info(
            alert_uuid=alert_uuid,
            alert_info=alert_info,
            event_count=5,
        )

        result = state_manager.get_alert_info(alert_uuid)
        assert result == alert_info

    def test_get_alert_info_returns_none_for_nonexistent(self, state_manager):
        """Test that get_alert_info returns None for non-existent alert."""
        result = state_manager.get_alert_info("nonexistent-alert")
        assert result is None

    def test_get_alerts_pending_time_check(self, state_manager):
        """Test that get_alerts_pending_time_check returns correct alerts."""
        now = datetime.now(timezone.utc)

        # Alert with pending events within time window
        state_manager._state["alerts"]["alert-pending"] = {
            "alert_uuid": "alert-pending",
            "alert_short_id": "ALT-PEND",
            "current_event_count": 10,
            "last_triggered_event_count": 5,
            "last_event_at": now.isoformat(),
            "last_triggered_at": (now - timedelta(hours=2)).isoformat(),
        }

        # Alert with no pending events
        state_manager._state["alerts"]["alert-no-pending"] = {
            "alert_uuid": "alert-no-pending",
            "alert_short_id": "ALT-NOPEND",
            "current_event_count": 5,
            "last_triggered_event_count": 5,
            "last_event_at": now.isoformat(),
            "last_triggered_at": now.isoformat(),
        }

        # Alert with old events (outside time window)
        state_manager._state["alerts"]["alert-old"] = {
            "alert_uuid": "alert-old",
            "alert_short_id": "ALT-OLD",
            "current_event_count": 10,
            "last_triggered_event_count": 5,
            "last_event_at": (now - timedelta(hours=3)).isoformat(),
            "last_triggered_at": (now - timedelta(hours=4)).isoformat(),
        }

        pending = state_manager.get_alerts_pending_time_check(time_window_hours=1)

        assert len(pending) == 1
        assert pending[0]["alert_uuid"] == "alert-pending"

    def test_get_all_alerts(self, state_manager):
        """Test that get_all_alerts returns all alert states."""
        state_manager._state["alerts"]["alert-1"] = {"alert_uuid": "alert-1"}
        state_manager._state["alerts"]["alert-2"] = {"alert_uuid": "alert-2"}
        state_manager._state["alerts"]["alert-3"] = {"alert_uuid": "alert-3"}

        all_alerts = state_manager.get_all_alerts()

        assert len(all_alerts) == 3
        assert "alert-1" in all_alerts
        assert "alert-2" in all_alerts
        assert "alert-3" in all_alerts


class TestAlertEventsThresholdTrigger_TimeThresholdThread:
    """Test periodic time threshold check thread."""

    def test_time_threshold_thread_starts_when_enabled(self, threshold_trigger):
        """Test that time threshold thread starts when enabled."""
        threshold_trigger.configuration["enable_time_threshold"] = True
        threshold_trigger._ensure_initialized()

        assert threshold_trigger._time_threshold_thread is not None
        assert threshold_trigger._time_threshold_thread.is_alive()

        # Clean up
        threshold_trigger._stop_time_threshold_thread()

    def test_time_threshold_thread_does_not_start_when_disabled(self, module_configuration, symphony_storage):
        """Test that time threshold thread does not start when disabled."""
        trigger = AlertEventsThresholdTrigger()
        trigger._data_path = symphony_storage
        trigger.module.configuration = module_configuration
        trigger.configuration = {
            "enable_volume_threshold": True,
            "enable_time_threshold": False,
        }
        trigger.log = MagicMock()

        trigger._ensure_initialized()

        assert trigger._time_threshold_thread is None

    def test_stop_time_threshold_thread(self, threshold_trigger):
        """Test that stop properly stops the time threshold thread."""
        threshold_trigger.configuration["enable_time_threshold"] = True
        threshold_trigger._ensure_initialized()

        # Thread should be running
        assert threshold_trigger._time_threshold_thread.is_alive()

        # Stop the thread
        threshold_trigger._stop_time_threshold_thread()

        # Thread should be stopped
        assert (
            threshold_trigger._time_threshold_thread is None or not threshold_trigger._time_threshold_thread.is_alive()
        )

    def test_check_pending_time_thresholds_triggers_alerts(self, threshold_trigger, sample_threshold_alert):
        """Test that _check_pending_time_thresholds triggers pending alerts."""
        threshold_trigger.configuration["enable_time_threshold"] = True
        threshold_trigger.configuration["time_window_hours"] = 1
        threshold_trigger._ensure_initialized()

        # Stop the auto-started thread to avoid interference
        threshold_trigger._stop_time_threshold_thread()

        now = datetime.now(timezone.utc)

        # Add a pending alert to the state and save it
        threshold_trigger.state_manager._state["alerts"]["alert-time-check"] = {
            "alert_uuid": "alert-time-check",
            "alert_short_id": "ALT-TIME",
            "current_event_count": 10,
            "last_triggered_event_count": 5,
            "last_event_at": now.isoformat(),
            "last_triggered_at": (now - timedelta(hours=2)).isoformat(),
            "alert_info": sample_threshold_alert,
            "rule_uuid": "rule-uuid",
            "rule_name": "Test Rule",
            "version": 1,
        }
        # Save state so it persists when _check_pending_time_thresholds reloads
        threshold_trigger.state_manager._save_state_to_s3()

        # Run the check
        threshold_trigger._check_pending_time_thresholds()

        # Verify send_event was called
        assert threshold_trigger.send_event.called

        # Verify context
        call_args = threshold_trigger.send_event.call_args
        event = call_args[1]["event"]
        assert event["trigger_context"]["reason"] == "time_threshold"

    def test_trigger_stop_method_stops_thread(self, threshold_trigger):
        """Test that the trigger's stop method stops the time threshold thread."""
        threshold_trigger.configuration["enable_time_threshold"] = True
        threshold_trigger._ensure_initialized()

        # Thread should be running
        assert threshold_trigger._time_threshold_thread.is_alive()

        # Call stop
        threshold_trigger.stop()

        # Thread should be stopped
        assert (
            threshold_trigger._time_threshold_thread is None or not threshold_trigger._time_threshold_thread.is_alive()
        )
