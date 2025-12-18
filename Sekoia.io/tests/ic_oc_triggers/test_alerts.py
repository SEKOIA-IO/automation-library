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
