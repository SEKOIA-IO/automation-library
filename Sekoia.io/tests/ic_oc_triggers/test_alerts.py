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
)


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
                "unseen": True
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
