import os
import time
from threading import Thread
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock
from netskope_api.iterator.netskope_iterator import NetskopeIterator
from sekoia_automation.exceptions import ModuleConfigurationError

from netskope_modules import NetskopeModule
from netskope_modules.connector_pull_events_v2 import NetskopeEventConnector, NetskopeEventConsumer
from netskope_modules.constants import MESSAGE_CANNOT_CONSUME_SERVICE
from netskope_modules.types import NetskopeAlertType, NetskopeEventType


@pytest.fixture
def trigger(symphony_storage):
    module = NetskopeModule()
    module._trigger_configuration_uuid = "ec92e51c-d45e-47b1-b820-29b97721623f"
    trigger = NetskopeEventConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "base_url": "https://my.fake.sekoia",
    }
    trigger.configuration = {
        "api_token": "api_token",
        "intake_key": "intake_key",
        "consumer_group": "",
    }
    return trigger


def test_user_agent(trigger):
    user_agent = trigger._user_agent
    assert user_agent is not None
    assert user_agent.startswith("sekoiaio-connector/netskope-")


def test_next_batch_sleep_until_next_round(trigger):
    with patch("netskope_modules.connector_pull_events_v2.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=200,
            json={
                "ok": 1,
                "analyze_result": True,
                "result": [
                    {
                        "timestamp": 1651424472,
                        "type": "admin_audit_logs",
                        "user": "john.doe@example.org",
                        "severity_level": 1,
                        "audit_log_event": "Events were cleared",
                        "supporting_data": {"data_type": None, "data_values": [""]},
                        "organization_unit": "",
                        "ur_normalized": "john.doe@example.org",
                        "ccl": "unknown",
                        "count": 1,
                        "_id": "c8aa61c9dc9d4c909965",
                        "userPrincipalName": "",
                        "sAMAccountName": "",
                    }
                ],
            },
        )
        iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        mock_time.sleep.assert_called_once_with(30 - batch_duration)


def test_next_batch_sleep_according_the_response(trigger):
    with patch("netskope_modules.connector_pull_events_v2.time") as mock_time, requests_mock.Mocker() as mock_requests:
        response_wait_time = 45
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=200,
            json={
                "ok": 1,
                "analyze_result": True,
                "result": [
                    {
                        "timestamp": 1651424472,
                        "type": "admin_audit_logs",
                        "user": "john.doe@example.org",
                        "severity_level": 1,
                        "audit_log_event": "Events were cleared",
                        "supporting_data": {"data_type": None, "data_values": [""]},
                        "organization_unit": "",
                        "ur_normalized": "john.doe@example.org",
                        "ccl": "unknown",
                        "count": 1,
                        "_id": "c8aa61c9dc9d4c909965",
                        "userPrincipalName": "",
                        "sAMAccountName": "",
                    }
                ],
                "wait_time": response_wait_time,
            },
        )
        iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        mock_time.sleep.assert_called_once_with(response_wait_time)


def test_long_next_batch_should_not_sleep(trigger):
    with patch("netskope_modules.connector_pull_events_v2.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=200,
            json={
                "ok": 1,
                "analyze_result": True,
                "result": [
                    {
                        "timestamp": 1651424472,
                        "type": "admin_audit_logs",
                        "user": "john.doe@example.org",
                        "severity_level": 1,
                        "audit_log_event": "Events were cleared",
                        "supporting_data": {"data_type": None, "data_values": [""]},
                        "organization_unit": "",
                        "ur_normalized": "john.doe@example.org",
                        "ccl": "unknown",
                        "count": 1,
                        "_id": "c8aa61c9dc9d4c909965",
                        "userPrincipalName": "",
                        "sAMAccountName": "",
                    }
                ],
            },
        )
        iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 45  # the batch lasts 45 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0


def test_next_batch_with_no_content(trigger):
    with patch("netskope_modules.connector_pull_events_v2.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=204,
            text="",
        )
        iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        mock_time.sleep.assert_called_once_with(30 - batch_duration)


def test_next_batch_with_error(trigger):
    with patch("netskope_modules.connector_pull_events_v2.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=404,
            text="This dataexporter does not exist",
        )
        iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        mock_time.sleep.assert_called_once_with(30 - batch_duration)


def test_next_batch_no_consume_service(trigger):
    with patch("netskope_modules.connector_pull_events_v2.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=403,
            json={"message": MESSAGE_CANNOT_CONSUME_SERVICE},
        )
        iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        consumer.stop = Mock()
        mock_time.time.return_value = 1666711174.0

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        assert consumer.stop.called
        assert not mock_time.sleep.called


def test_next_batch_403_service(trigger):
    with patch("netskope_modules.connector_pull_events_v2.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=403,
            text="message",
        )
        iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        consumer.stop = Mock()
        mock_time.time.return_value = 1666711174.0

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        assert mock_time.sleep.called


def test_create_iterators(trigger):
    iterators = trigger.create_iterators(trigger.dataexports)

    # assert we create as many iterators as data exports
    assert len(iterators) == len(trigger.dataexports)

    for iterator in iterators.values():
        assert isinstance(iterator, NetskopeIterator)


def test_start_consumers(trigger):
    with patch.object(NetskopeEventConsumer, "start") as mock_start:
        iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
        iterators = {"alert-dlp": iterator}

        consumers = trigger.start_consumers(iterators)

        assert consumers is not None
        assert consumers.get("alert-dlp") is not None
        assert mock_start.called


def test_supervice_consumers(trigger):
    with patch.object(NetskopeEventConsumer, "start") as mock_start:
        alert_dlp_iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
        event_page_iterator = trigger.create_iterator(NetskopeEventType.PAGE, None)
        event_incident_iterator = trigger.create_iterator(NetskopeEventType.INCIDENT, None)
        event_network_iterator = trigger.create_iterator(NetskopeEventType.NETWORK, None)
        iterators = {
            "alert-dlp": alert_dlp_iterator,
            "page": event_page_iterator,
            "incident": event_incident_iterator,
            "network": event_network_iterator,
        }

        consumers = {
            "alert-dlp": Mock(**{"is_alive.return_value": False, "running": True}),
            "page": None,
            "incident": Mock(**{"is_alive.return_value": True, "running": True}),
            "network": Mock(**{"is_alive.return_value": False, "running": False}),
        }

        trigger.supervise_consumers(consumers, iterators)

        assert mock_start.call_count == 2


def test_stop_consumers(trigger):
    alert_dlp_iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
    event_page_iterator = trigger.create_iterator(NetskopeEventType.PAGE, None)
    event_incident_iterator = trigger.create_iterator(NetskopeEventType.INCIDENT, None)
    iterators = {
        "alert-dlp": alert_dlp_iterator,
        "page": event_page_iterator,
        "incident": event_incident_iterator,
    }

    consumers = {
        "alert-dlp": Mock(**{"is_alive.return_value": False}),
        "page": None,
        "incident": Mock(**{"is_alive.return_value": True}),
    }

    trigger.stop_consumers(consumers, iterators)

    incident_consumer = consumers.get("incident")
    assert incident_consumer is not None
    assert incident_consumer.stop.called


def test_undefined_base_url_should_raise_exception(symphony_storage):
    module = NetskopeModule()
    module._community_uuid = "ec92e51c-d45e-47b1-b820-29b97721623f"
    trigger = NetskopeEventConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "base_url": None,
    }
    trigger.configuration = {
        "api_token": "api_token",
        "intake_key": "intake_key",
    }
    with pytest.raises(ModuleConfigurationError):
        trigger.run()


@pytest.mark.skipif("{'NETSKOPE_BASE_URL', 'NETSKOPE_API_TOKEN'}" ".issubset(os.environ.keys()) == False")
def test_fetch_next_batch_integration(symphony_storage):
    module = NetskopeModule()
    module._community_uuid = "ec92e51c-d45e-47b1-b820-29b97721623f"
    trigger = NetskopeEventConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "base_url": os.environ["NETSKOPE_BASE_URL"],
    }
    trigger.configuration = {
        "api_token": os.environ["NETSKOPE_API_TOKEN"],
        "intake_key": "0123456789",
    }
    iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
    consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)

    with patch("netskope_modules.connector_pull_events_v2.time") as mock_time:
        mock_time.time.return_value = 1666711174.0
        consumer.next_batch()

    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0


@pytest.mark.skipif("{'NETSKOPE_BASE_URL', 'NETSKOPE_API_TOKEN'}" ".issubset(os.environ.keys()) == False")
def test_run_integration(symphony_storage):
    module = NetskopeModule()
    module._community_uuid = "ec92e51c-d45e-47b1-b820-29b97721623f"
    trigger = NetskopeEventConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "base_url": os.environ["NETSKOPE_BASE_URL"],
    }
    trigger.configuration = {
        "api_token": os.environ["NETSKOPE_API_TOKEN"],
        "intake_key": "0123456789",
    }
    main_thread = Thread(target=trigger.run)
    main_thread.start()

    # wait few seconds
    time.sleep(5)
    trigger._stop_event.set()

    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0
