import json
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

        should_trigger, context = threshold_trigger._evaluate_thresholds(sample_threshold_alert, previous_state=None)

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

        sample_threshold_alert["events_count"] = 150  # 100 new events

        with patch.object(threshold_trigger, "_count_events_in_time_window", return_value=0):
            should_trigger, context = threshold_trigger._evaluate_thresholds(sample_threshold_alert, previous_state)

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

        sample_threshold_alert["events_count"] = 150  # Only 50 new events (below 100 threshold)

        should_trigger, context = threshold_trigger._evaluate_thresholds(sample_threshold_alert, previous_state)

        assert should_trigger is False
        assert context["reason"] == "no_threshold_met"

    def test_no_new_events_does_not_trigger(self, threshold_trigger, sample_threshold_alert):
        """Test that alerts with no new events do not trigger."""
        threshold_trigger._ensure_initialized()

        previous_state = {
            "last_triggered_event_count": 150,
            "version": 1,
        }

        sample_threshold_alert["events_count"] = 150

        should_trigger, context = threshold_trigger._evaluate_thresholds(sample_threshold_alert, previous_state)

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
        assert any(
            "Alert locks cache at capacity" in str(call)
            for call in threshold_trigger.log.call_args_list
        )

        # Release locks
        for lock in locks:
            lock.release()


class TestAlertStateManager:
    """Test AlertStateManager functionality."""

    def test_get_nonexistent_alert_returns_none(self, tmp_path):
        """Test that getting a non-existent alert returns None."""
        state_path = tmp_path / "test_state.json"
        manager = AlertStateManager(state_path)

        state = manager.get_alert_state("nonexistent-uuid")
        assert state is None

    def test_update_alert_state_creates_new(self, tmp_path):
        """Test creating a new alert state."""
        state_path = tmp_path / "test_state.json"
        manager = AlertStateManager(state_path)

        manager.update_alert_state(
            alert_uuid="test-uuid",
            alert_short_id="ALT-99999",
            rule_uuid="rule-uuid",
            rule_name="Test Rule",
            event_count=50,
        )

        state = manager.get_alert_state("test-uuid")
        assert state is not None
        assert state["alert_short_id"] == "ALT-99999"
        assert state["last_triggered_event_count"] == 50
        assert state["total_triggers"] == 1

    def test_update_alert_state_increments_triggers(self, tmp_path):
        """Test that updating state increments trigger count."""
        from datetime import datetime, timedelta, timezone

        state_path = tmp_path / "test_state.json"
        manager = AlertStateManager(state_path)

        # First update
        manager.update_alert_state(
            alert_uuid="test-uuid",
            alert_short_id="ALT-99999",
            rule_uuid="rule-uuid",
            rule_name="Test Rule",
            event_count=50,
        )

        # Second update
        manager.update_alert_state(
            alert_uuid="test-uuid",
            alert_short_id="ALT-99999",
            rule_uuid="rule-uuid",
            rule_name="Test Rule",
            event_count=150,
        )

        state = manager.get_alert_state("test-uuid")
        assert state["last_triggered_event_count"] == 150
        assert state["total_triggers"] == 2

    def test_cleanup_old_states(self, tmp_path):
        """Test cleanup of old alert states."""
        from datetime import datetime, timedelta, timezone

        state_path = tmp_path / "test_state.json"
        manager = AlertStateManager(state_path)

        now = datetime.now(timezone.utc)

        # Create old alert (60 days ago)
        manager._state["alerts"]["old-alert"] = {
            "alert_uuid": "old-alert",
            "last_triggered_at": (now - timedelta(days=60)).isoformat(),
            "last_triggered_event_count": 100,
        }
        manager._save_state()

        # Create recent alert
        manager.update_alert_state(
            alert_uuid="recent-alert",
            alert_short_id="ALT-11111",
            rule_uuid="rule-uuid",
            rule_name="Recent Rule",
            event_count=50,
        )

        # Cleanup entries older than 30 days
        cutoff = now - timedelta(days=30)
        removed = manager.cleanup_old_states(cutoff)

        assert removed == 1
        assert manager.get_alert_state("old-alert") is None
        assert manager.get_alert_state("recent-alert") is not None


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
