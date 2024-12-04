import datetime
import threading
import time
from dataclasses import dataclass
from datetime import UTC
from unittest.mock import MagicMock, call, patch

import pytest
from freezegun import freeze_time
from management.mgmtsdk_v2.exceptions import UnauthorizedException

from sentinelone_module.logs.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


@dataclass
class MockResponse:
    data: list
    pagination: dict


@freeze_time("1970-01-01 00:00:00")
def test_pull_activities(activity_consumer, activity_1, activity_2):
    OUTCOMING_EVENTS.labels = MagicMock()
    EVENTS_LAG.labels = MagicMock()
    most_recent_datetime_seen = datetime.datetime(2024, 1, 23, 11, 6, 34)

    # Test timestamp caching
    activity_1.createdAt = None

    response_1 = MockResponse(pagination={"nextCursor": "foo"}, data=[activity_1])
    response_2 = MockResponse(pagination={"nextCursor": None}, data=[activity_2])
    activity_consumer.management_client.activities.get.side_effect = [response_1, response_2]
    activity_consumer.pull_events(most_recent_datetime_seen)

    assert activity_consumer.management_client.activities.get.call_count == 2
    assert activity_consumer.connector.push_events_to_intakes.call_args_list == [
        call(activity_consumer._serialize_events([activity_1])),
        call(activity_consumer._serialize_events([activity_2])),
    ]

    assert OUTCOMING_EVENTS.labels(intake_key=activity_consumer.configuration.intake_key).inc.call_args_list == [
        call(1),
        call(1),
    ]
    assert EVENTS_LAG.labels(
        intake_key=activity_consumer.configuration.intake_key, type="activities"
    ).set.call_args_list == [
        call(0),
        call(
            int((datetime.datetime.now(UTC) - datetime.datetime.fromisoformat(activity_2.createdAt)).total_seconds())
        ),
    ]


@freeze_time("1970-01-01 00:00:00")
def test_pull_activities_donot_collect_activity_twice(activity_consumer, activity_1, activity_2):
    OUTCOMING_EVENTS.labels = MagicMock()
    EVENTS_LAG.labels = MagicMock()
    most_recent_datetime_seen = datetime.datetime(2024, 1, 23, 11, 6, 34)

    activity_consumer.management_client.activities.get.return_value = MockResponse(
        pagination={"nextCursor": None}, data=[activity_1]
    )
    activity_consumer.pull_events(most_recent_datetime_seen)
    activity_consumer.pull_events(most_recent_datetime_seen)

    assert activity_consumer.connector.push_events_to_intakes.call_args_list == [
        call(activity_consumer._serialize_events([activity_1])),
    ]


@freeze_time("1970-01-01 00:00:00")
def test_pull_threats(threat_consumer, threat_1, threat_2):
    OUTCOMING_EVENTS.labels = MagicMock()
    EVENTS_LAG.labels = MagicMock()
    most_recent_datetime_seen = datetime.datetime(2024, 1, 23, 11, 6, 34)

    response_1 = MockResponse(pagination={"nextCursor": "foo"}, data=[threat_1])
    response_2 = MockResponse(pagination={"nextCursor": None}, data=[threat_2])
    threat_consumer.management_client.client.get.side_effect = [response_1, response_2]
    threat_consumer.pull_events(most_recent_datetime_seen)

    assert threat_consumer.management_client.client.get.call_count == 2
    assert threat_consumer.connector.push_events_to_intakes.call_args_list == [
        call(threat_consumer._serialize_events([threat_1])),
        call(threat_consumer._serialize_events([threat_2])),
    ]

    assert OUTCOMING_EVENTS.labels(intake_key=threat_consumer.configuration.intake_key).inc.call_args_list == [
        call(1),
        call(1),
    ]
    assert EVENTS_LAG.labels(
        intake_key=threat_consumer.configuration.intake_key, type="threats"
    ).set.call_args_list == [
        call(
            int((datetime.datetime.now(UTC) - datetime.datetime.fromisoformat(threat_1["createdAt"])).total_seconds())
        ),
        call(
            int((datetime.datetime.now(UTC) - datetime.datetime.fromisoformat(threat_2["createdAt"])).total_seconds())
        ),
    ]


@freeze_time("1970-01-01 00:00:00")
def test_pull_threats_donot_collect_threats_twice(threat_consumer, threat_1, threat_2):
    OUTCOMING_EVENTS.labels = MagicMock()
    EVENTS_LAG.labels = MagicMock()
    most_recent_datetime_seen = datetime.datetime(2024, 1, 23, 11, 6, 34)

    threat_consumer.management_client.client.get.return_value = MockResponse(
        pagination={"nextCursor": None}, data=[threat_1]
    )
    threat_consumer.pull_events(most_recent_datetime_seen)
    threat_consumer.pull_events(most_recent_datetime_seen)

    assert threat_consumer.connector.push_events_to_intakes.call_args_list == [
        call(threat_consumer._serialize_events([threat_1])),
    ]


def test_run_consumer(activity_consumer):
    def sleeper(_):
        time.sleep(0.1)

    FORWARD_EVENTS_DURATION.labels = MagicMock()

    with (
        patch.object(activity_consumer, "pull_events") as pull_events,
        patch("sentinelone_module.logs.connector.sleep") as sleep2,
    ):
        sleep2.side_effect = sleeper

        t = threading.Thread(target=activity_consumer.run)
        t.start()
        time.sleep(0.1)
        activity_consumer.stop()
        t.join()

        pull_events.assert_called()
        FORWARD_EVENTS_DURATION.labels(intake_key=activity_consumer.configuration.intake_key).observe.assert_called()


def test_run_consumer_fail_get_info(activity_consumer):
    activity_consumer.management_client.system.get_info.side_effect = UnauthorizedException
    with pytest.raises(UnauthorizedException):
        activity_consumer.run()
    activity_consumer.log.assert_called_once_with(
        f"Connector is unauthorized to retrieve system info", level="warning"
    )


def test_start_consumers(connector, activity_consumer, threat_consumer):
    with patch("sentinelone_module.logs.connector.SentinelOneLogsConsumer.start") as start_mock:
        results = connector.start_consumers()
        assert list(results.keys()) == ["activity", "threat"]
        assert start_mock.call_count == 2


def test_supervise_consumers(connector, activity_consumer, threat_consumer):
    consumers = {"activity": activity_consumer, "threat": None}

    with patch("sentinelone_module.logs.connector.SentinelOneLogsConsumer.start") as start_mock:
        connector.supervise_consumers(consumers)

        assert connector.log.call_args_list == [
            call(message="Restarting activity consumer", level="info"),
            call(message="Restarting threat consumer", level="info"),
        ]

        assert start_mock.call_count == 2


def test_stop_consumers(connector, activity_consumer, threat_consumer):
    activity_consumer.is_alive.return_value = True
    threat_consumer.is_alive.return_value = False
    consumers = {"activity": activity_consumer, "threat": threat_consumer}

    with (
        patch.object(activity_consumer, "stop") as activity_stop,
        patch.object(threat_consumer, "stop") as threat_stop,
    ):
        connector.stop_consumers(consumers)
        connector.log.assert_called_once_with(message="Stopping activity consumer", level="info")

        activity_stop.assert_called_once()
        threat_stop.assert_not_called()


def test_run_connector(connector):
    def sleeper(_):
        time.sleep(0.1)

    d = {"foo": "bar"}
    with (
        patch("sentinelone_module.logs.connector.sleep") as sleep2,
        patch.object(connector, "start_consumers", return_value=d) as start_consumers,
        patch.object(connector, "supervise_consumers") as supervise_consumers,
        patch.object(connector, "stop_consumers") as stop_consumers,
    ):
        sleep2.side_effect = sleeper

        t = threading.Thread(target=connector.run)
        t.start()
        time.sleep(0.1)
        connector.stop()
        t.join()

        start_consumers.assert_called_once()
        supervise_consumers.assert_called_with(d)
        stop_consumers.assert_called_once_with(d)
