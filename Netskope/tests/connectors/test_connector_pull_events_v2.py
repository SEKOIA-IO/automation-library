import time
from threading import Thread
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock
from netskope_api.iterator.netskope_iterator import NetskopeIterator
from requests.exceptions import ConnectionError
from sekoia_automation.exceptions import ModuleConfigurationError

from netskope_modules.connectors.connector_pull_events_v2 import NetskopeEventConsumer
from netskope_modules.constants import MESSAGE_CANNOT_CONSUME_SERVICE
from netskope_modules.types import NetskopeAlertType, NetskopeEventType


def test_user_agent(trigger):
    user_agent = trigger._user_agent
    assert user_agent is not None
    expected_prefix = f"sekoiaio-connector/{trigger.module.manifest.get('slug')}-"
    assert user_agent.startswith(expected_prefix)


def test_next_batch_sleep_until_next_round(trigger):
    with (
        patch("netskope_modules.connectors.connector_pull_events_v2.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
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
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        mock_time.sleep.assert_called_once_with(30 - batch_duration)


def test_next_batch_sleep_according_the_response(trigger):
    with (
        patch("netskope_modules.connectors.connector_pull_events_v2.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
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
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        mock_time.sleep.assert_called_once_with(response_wait_time)


def test_long_next_batch_should_not_sleep(trigger):
    with (
        patch("netskope_modules.connectors.connector_pull_events_v2.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
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
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 45  # the batch lasts 45 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0


def test_next_batch_with_no_content(trigger):
    with (
        patch("netskope_modules.connectors.connector_pull_events_v2.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=204,
            text="",
        )
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        mock_time.sleep.assert_called_once_with(30 - batch_duration)


def test_next_batch_with_error(trigger):
    with (
        patch("netskope_modules.connectors.connector_pull_events_v2.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=404,
            text="This dataexporter does not exist",
        )
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        mock_time.sleep.assert_called_once_with(30 - batch_duration)


def test_next_batch_no_consume_service(trigger):
    with (
        patch("netskope_modules.connectors.connector_pull_events_v2.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=403,
            json={"message": MESSAGE_CANNOT_CONSUME_SERVICE},
        )
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        consumer.stop = Mock()
        mock_time.time.return_value = 1666711174.0

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        assert consumer.stop.called
        assert not mock_time.sleep.called


def test_next_batch_invalid_api_token(trigger):
    with patch(
        "netskope_modules.connectors.connector_pull_events_v2.time"
    ) as mock_time:
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        iterator.client.get = MagicMock(
            side_effect=ValueError(
                "Invalid API token TOKEN configured to access the endpoint https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp"
            )
        )

        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        consumer.stop = Mock()

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        assert consumer.stop.called
        assert not mock_time.sleep.called


def test_consumer_stop_changes_running_state(trigger):
    iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
    consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)

    assert consumer.running
    consumer.stop()
    assert not consumer.running


def test_next_batch_connection_aborted_is_ignored(trigger):
    iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
    iterator.client.get = MagicMock(
        side_effect=ConnectionError("Connection aborted by peer")
    )

    consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)

    consumer.next_batch()

    assert trigger.push_events_to_intakes.call_count == 0


def test_next_batch_connection_error_is_raised(trigger):
    iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
    iterator.client.get = MagicMock(
        side_effect=ConnectionError("TLS handshake failure")
    )

    consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)

    with pytest.raises(ConnectionError, match="TLS handshake failure"):
        consumer.next_batch()


def test_next_batch_unhandled_value_error_is_raised(trigger):
    iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
    iterator.client.get = MagicMock(side_effect=ValueError("unexpected value error"))

    consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)

    with pytest.raises(ValueError, match="unexpected value error"):
        consumer.next_batch()


def test_next_batch_403_service(trigger):
    with (
        patch("netskope_modules.connectors.connector_pull_events_v2.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=403,
            text="message",
        )
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        consumer.stop = Mock()
        mock_time.time.return_value = 1666711174.0

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        assert mock_time.sleep.called


def test_next_batch_403_service_with_json_error_message(trigger):
    with (
        patch("netskope_modules.connectors.connector_pull_events_v2.time") as mock_time,
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            "https://my.fake.sekoia/api/v2/events/dataexport/alerts/dlp",
            status_code=403,
            json={"message": "custom 403 error"},
        )
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
        mock_time.time.return_value = 1666711174.0

        consumer.next_batch()

        assert trigger.push_events_to_intakes.call_count == 0
        trigger.log.assert_any_call(
            message="Cannot consume the service alert-dlp. Error=custom 403 error",
            level="error",
        )


def test_create_iterators(trigger):
    iterators = trigger.create_iterators(trigger.dataexports)

    # assert we create as many iterators as data exports
    assert len(iterators) == len(trigger.dataexports)

    for iterator in iterators.values():
        assert isinstance(iterator, NetskopeIterator)


def test_dataexports_security_check_only(trigger):
    trigger.configuration.security_check_only = True
    trigger.__dict__.pop("dataexports", None)

    dataexports = trigger.dataexports

    assert dataexports == [
        (NetskopeEventType.ALERT, NetskopeAlertType.MALWARE),
        (NetskopeEventType.ALERT, NetskopeAlertType.MALSITE),
        (NetskopeEventType.ALERT, NetskopeAlertType.DLP),
    ]


def test_configuration_uuid_prefers_connector_configuration_uuid(trigger):
    trigger.module._connector_configuration_uuid = "connector-uuid"
    trigger.__dict__.pop("configuration_uuid", None)

    assert trigger.configuration_uuid == "connector-uuid"


def test_get_index_name_uses_consumer_group_when_set(trigger):
    trigger.configuration.consumer_group = "shared-group"

    index_name = trigger.get_index_name(NetskopeEventType.ALERT, NetskopeAlertType.DLP)

    assert index_name == "shared-group"


def test_create_iterator_alert_requires_alert_type(trigger):
    with pytest.raises(ValueError, match="alert_type cannot be null"):
        trigger.create_iterator(NetskopeEventType.ALERT, None)


def test_start_consumers(trigger):
    with patch.object(NetskopeEventConsumer, "start") as mock_start:
        iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        iterators = {"alert-dlp": iterator}

        consumers = trigger.start_consumers(iterators)

        assert consumers is not None
        assert consumers.get("alert-dlp") is not None
        assert mock_start.called


def test_supervise_consumers(trigger):
    with patch.object(NetskopeEventConsumer, "start") as mock_start:
        alert_dlp_iterator = trigger.create_iterator(
            NetskopeEventType.ALERT, NetskopeAlertType.DLP
        )
        event_page_iterator = trigger.create_iterator(NetskopeEventType.PAGE, None)
        event_incident_iterator = trigger.create_iterator(
            NetskopeEventType.INCIDENT, None
        )
        event_network_iterator = trigger.create_iterator(
            NetskopeEventType.NETWORK, None
        )
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
    alert_dlp_iterator = trigger.create_iterator(
        NetskopeEventType.ALERT, NetskopeAlertType.DLP
    )
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


def test_undefined_base_url_should_raise_exception(trigger):
    trigger.module.configuration.base_url = None
    with pytest.raises(ModuleConfigurationError):
        trigger.run()


def test_consumer_run_logs_exception(trigger):
    iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
    consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)
    consumer.next_batch = Mock(side_effect=RuntimeError("boom"))

    consumer.run()

    trigger.log_exception.assert_called_once()


def test_run_supervises_consumers_and_stops_them(trigger):
    trigger._stop_event.clear()
    iterators = {"alert-dlp": Mock()}
    consumers = {"alert-dlp": Mock()}

    def stop_after_first_supervision(*args, **kwargs):
        trigger._stop_event.set()

    with (
        patch.object(trigger, "create_iterators", return_value=iterators),
        patch.object(trigger, "start_consumers", return_value=consumers),
        patch.object(
            trigger, "supervise_consumers", side_effect=stop_after_first_supervision
        ) as mock_supervise,
        patch.object(trigger, "stop_consumers") as mock_stop,
        patch(
            "netskope_modules.connectors.connector_pull_events_v2.time.sleep"
        ) as mock_sleep,
    ):
        trigger.run()

    mock_supervise.assert_called_once_with(consumers, iterators)
    mock_sleep.assert_called_once_with(5)
    mock_stop.assert_called_once_with(consumers, iterators)


def test_run_logs_exception_when_consumer_start_fails(trigger):
    with patch.object(
        trigger, "create_iterators", side_effect=RuntimeError("iterators failed")
    ):
        trigger.run()

    trigger.log_exception.assert_called_once()


@pytest.mark.skipif(
    "{'NETSKOPE_BASE_URL', 'NETSKOPE_API_TOKEN'}.issubset(os.environ.keys()) == False"
)
def test_fetch_next_batch_integration(integration_trigger):
    trigger = integration_trigger
    iterator = trigger.create_iterator(NetskopeEventType.ALERT, NetskopeAlertType.DLP)
    consumer = NetskopeEventConsumer(trigger, "alert-dlp", iterator)

    with patch(
        "netskope_modules.connectors.connector_pull_events_v2.time"
    ) as mock_time:
        mock_time.time.return_value = 1666711174.0
        consumer.next_batch()

    calls = [
        call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list
    ]
    assert len(calls) > 0


@pytest.mark.skipif(
    "{'NETSKOPE_BASE_URL', 'NETSKOPE_API_TOKEN'}.issubset(os.environ.keys()) == False"
)
def test_run_integration(integration_trigger):
    trigger = integration_trigger
    main_thread = Thread(target=trigger.run)
    main_thread.start()

    # wait few seconds
    time.sleep(5)
    trigger._stop_event.set()

    calls = [
        call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list
    ]
    assert len(calls) > 0
