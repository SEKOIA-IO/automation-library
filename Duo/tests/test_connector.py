from unittest.mock import MagicMock, Mock, patch

import pytest

from duo import DuoModule, LogType
from duo.connector import DuoAdminLogsConnector, DuoLogsConsumer


@pytest.fixture
def trigger(data_storage):
    module = DuoModule()
    trigger = DuoAdminLogsConnector(module=module, data_path=data_storage)

    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "secret_key": "somekey",
        "integration_key": "key123",
        "hostname": "api-XXXXXXXX.duosecurity.com",
    }
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60}
    yield trigger


@pytest.fixture
def telephony_response_1():
    return {
        "items": [
            {
                "context": "enrollment",
                "credits": 1,
                "phone": "+12125556707",
                "telephony_id": "220f89ff-bff8-4466-b6cb-b7787940ce68",
                "ts": "2023-03-21T22:34:49.466370+00:00",
                "txid": "2f5d34d3-053f-422c-9dd4-77a5d58706b1",
                "type": "sms",
            }
        ],
        "metadata": {"next_offset": "offset_token"},
    }


@pytest.fixture
def telephony_response_2():
    return {"items": []}


@pytest.fixture
def admin_response_1():
    return [
        {
            "action": "user_update",
            "description": '{"notes": "Joe asked for their nickname to be displayed instead of Joseph.", "realname": "Joe Smith"}',
            "isotimestamp": "2020-01-24T15:09:42+00:00",
            "object": "jsmith",
            "timestamp": 1579878582,
            "username": "admin",
        }
    ]


@pytest.fixture
def admin_response_2():
    return []


def test_fetch_batches_v2(trigger, telephony_response_1, telephony_response_2):
    with patch(
        "duo_client.logs.Telephony.get_telephony_logs_v2", side_effect=[telephony_response_1, telephony_response_2]
    ) as mock_get_log, patch(
        "duo.connector.DuoLogsConsumer.load_checkpoint", return_value={"min_time": 1687598073}
    ) as mock_load_checkpoint, patch(
        "duo.connector.DuoLogsConsumer.save_checkpoint"
    ) as mock_save_checkpoint, patch(
        "duo.connector.time"
    ) as mock_time:
        # create a consumer
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer = DuoLogsConsumer(connector=trigger, log_type=LogType.TELEPHONY)
        consumer.fetch_batches()

        assert trigger.push_events_to_intakes.call_count == 1

        mock_time.sleep.assert_called_once_with(44)


def test_fetch_batches_v1(trigger, admin_response_1, admin_response_2):
    with patch(
        "duo_client.Admin.get_administrator_log", side_effect=[admin_response_1, admin_response_2]
    ) as mock_get_log, patch(
        "duo.connector.DuoLogsConsumer.load_checkpoint", return_value={}
    ) as mock_load_checkpoint, patch(
        "duo.connector.DuoLogsConsumer.save_checkpoint"
    ) as mock_save_checkpoint, patch(
        "duo.connector.time"
    ) as mock_time:
        # create a consumer
        batch_duration = 42  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        consumer = DuoLogsConsumer(connector=trigger, log_type=LogType.ADMINISTRATION)
        consumer.fetch_batches()

        assert trigger.push_events_to_intakes.call_count == 1

        mock_time.sleep.assert_called_once_with(18)


def test_fetch_batches_with_no_events(trigger):
    with patch("duo_client.Admin.get_administrator_log", side_effect=[]) as mock_get_log, patch(
        "duo.connector.DuoLogsConsumer.load_checkpoint", return_value={}
    ) as mock_load_checkpoint, patch("duo.connector.DuoLogsConsumer.save_checkpoint") as mock_save_checkpoint, patch(
        "duo.connector.time"
    ) as mock_time:
        consumer = DuoLogsConsumer(connector=trigger, log_type=LogType.ADMINISTRATION)
        consumer.fetch_batches()

        assert trigger.push_events_to_intakes.call_count == 0
        mock_time.sleep.assert_called_once_with(trigger.configuration.frequency)


def test_fetch_batches_with_non_existent_log_type(trigger):
    with patch("duo.connector.DuoLogsConsumer.load_checkpoint", return_value={}) as mock_load_checkpoint, patch(
        "duo.connector.DuoLogsConsumer.save_checkpoint"
    ) as mock_save_checkpoint:
        consumer = DuoLogsConsumer(connector=trigger, log_type="TEST")

        with pytest.raises(NotImplementedError) as context:
            consumer.fetch_batches()

        assert trigger.push_events_to_intakes.call_count == 0


def test_start_consumers(trigger):
    with patch("duo.connector.DuoLogsConsumer.start") as mock_start:
        consumers = trigger.start_consumers()

        assert consumers is not None

        assert LogType.ADMINISTRATION in consumers
        assert LogType.AUTHENTICATION in consumers
        assert LogType.TELEPHONY in consumers
        assert LogType.OFFLINE in consumers

        assert mock_start.called


def test_supervise_consumers(trigger):
    with patch("duo.connector.DuoLogsConsumer.start") as mock_start:
        consumers = {
            LogType.AUTHENTICATION: Mock(**{"is_alive.return_value": False, "running": True}),
            LogType.ADMINISTRATION: None,
            LogType.TELEPHONY: Mock(**{"is_alive.return_value": True, "running": True}),
            LogType.OFFLINE: Mock(**{"is_alive.return_value": False, "running": False}),
        }

        trigger.supervise_consumers(consumers)
        assert mock_start.call_count == 2


def test_stop_consumers(trigger):
    consumers = {
        LogType.AUTHENTICATION: Mock(**{"is_alive.return_value": False}),
        LogType.ADMINISTRATION: None,
        LogType.TELEPHONY: Mock(**{"is_alive.return_value": False}),
        LogType.OFFLINE: Mock(**{"is_alive.return_value": True}),
    }

    trigger.stop_consumers(consumers)

    offline_consumer = consumers.get(LogType.OFFLINE)
    assert offline_consumer is not None
    assert offline_consumer.stop.called


def test_checkpoint(trigger):
    consumer = DuoLogsConsumer(connector=trigger, log_type=LogType.TELEPHONY)

    consumer.save_checkpoint(offset={"some_key": "some_value"})
    result = consumer.load_checkpoint()

    assert result == {"offset": {"some_key": "some_value"}}
