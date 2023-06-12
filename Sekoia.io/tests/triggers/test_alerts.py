import json
from unittest.mock import MagicMock, Mock

import pytest
import requests_mock

from sekoiaio.triggers.alerts import AlertCreatedTrigger, SecurityAlertsTrigger


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
    alert_trigger.handle_alert = Mock()

    for message in sample_notifications:
        alert_trigger.handler_dispatcher(json.dumps(message))
        alert_trigger.handle_alert.assert_called()


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


def test_securityalertstrigger_handle_alert_send_message(
    alert_trigger,
    sample_notifications,
    sample_sicalertapi_mock,
    sample_sicalertapi,
):
    alert_trigger.send_event = MagicMock()

    with sample_sicalertapi_mock:
        notification = sample_notifications[0]
        alert_trigger.handle_alert(notification)

        # `send_event()` should be called once with defined
        # arguments. We only test a subset of arguments send.
        alert_trigger.send_event.assert_called_once()

        args, kwargs = alert_trigger.send_event.call_args

        for entry in ["directory", "event", "event_name", "remove_directory"]:
            assert kwargs.get(entry) is not None

        evt = kwargs.get("event")
        assert evt.get("file_path") == "alert.json"
        assert evt.get("alert_uuid") == notification.get("attributes").get("alert_uuid")


@pytest.fixture
def alert_created_trigger(module_configuration, symphony_storage):
    alert_created_trigger = AlertCreatedTrigger()
    alert_created_trigger.configuration = {}
    alert_created_trigger._data_path = symphony_storage
    alert_created_trigger.module.configuration = module_configuration
    alert_created_trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"

    yield alert_created_trigger


def test_single_event_triggers(alert_created_trigger, sample_sicalertapi_mock, sample_notifications):
    alert_created_trigger.send_event = MagicMock()

    with sample_sicalertapi_mock:
        # Calling the trigger with an alert created notification should create an event
        alert_created_trigger.handle_alert(sample_notifications[0])
        alert_created_trigger.send_event.assert_called_once()

        # All other notification types should not
        for notification in sample_notifications[1:]:
            alert_created_trigger.handle_alert(notification)

        alert_created_trigger.send_event.assert_called_once()


def test_alert_trigger_filter_by_rule(
    alert_trigger, sample_notifications, sample_sicalertapi_mock, sample_sicalertapi
):
    alert_trigger.send_event = MagicMock()
    with sample_sicalertapi_mock:
        # no match
        alert_trigger.configuration = {"rule_filter": "foo"}
        alert_trigger.handle_alert(sample_notifications[0])
        assert not alert_trigger.send_event.called

        # match rule name
        alert_trigger.configuration = {"rule_filter": sample_sicalertapi["rule"]["name"]}
        alert_trigger.handle_alert(sample_notifications[0])
        assert alert_trigger.send_event.called

        alert_trigger.send_event.reset_mock()

        # match rule uuid
        alert_trigger.configuration = {"rule_filter": sample_sicalertapi["rule"]["uuid"]}
        alert_trigger.handle_alert(sample_notifications[0])
        assert alert_trigger.send_event.called
