import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import sleep
from unittest.mock import patch

from prometheus_client import Counter

from office365.management_api.connector import FORWARD_EVENTS_DURATION
from office365.management_api.errors import FailedToActivateO365Subscription


@patch.object(Counter, "inc")
def test_forward_events(mock_prometheus, connector, event):
    connector.forward_events([event])
    connector.log.assert_called_once_with("Pushing 1 event(s) to intake", level="info")
    mock_prometheus.assert_called_once()
    connector.push_events_to_intakes.assert_called_once_with([event])


def test_activate_subscriptions_client_exception(connector):
    connector.client.activate_subscriptions.side_effect = FailedToActivateO365Subscription()

    connector.activate_subscriptions()

    connector.client.activate_subscriptions.assert_called_once()
    connector.log_exception.assert_called_once()

    call_args = connector.log_exception.call_args_list[0].kwargs
    assert len(call_args) == 2
    assert call_args["message"] == "An exception occurred when trying to subscribe to Office365 events."
    assert isinstance(call_args["exception"], FailedToActivateO365Subscription)


def test_pull_content(connector, event):
    connector.client.list_subscriptions.return_value = ["json"]
    connector.client.get_subscription_contents.return_value = [[{"contentUri": " foo://example.com"}]]
    connector.client.get_content.return_value = [event]

    result = connector.pull_content(datetime.now() - timedelta(minutes=10), datetime.now())
    assert len(result) == 1
    assert json.loads(result[0]) == event


def test_split_date_range(connector):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(minutes=31)
    delta = timedelta(minutes=30)
    split = connector._split_date_range(start_date, end_date, delta)

    assert split == [(start_date, start_date + delta), (start_date + delta, end_date)]


def test_last_pull_date(connector, freezer):
    now = datetime.now(UTC)

    # Not set
    with patch.object(Path, "read_text", side_effect=FileNotFoundError):
        # Timedelta is sligthly less than 7 days since a few microseconds elapsed between `now`
        # and the moment `last_pull_date` is generated
        assert now == connector.last_pull_date

    # Less than 7 days ago
    connector.last_pull_date = now
    assert connector.last_pull_date == now

    # More than 7 days ago
    connector.last_pull_date = now - timedelta(days=365)
    # Timedelta is sligthly less than 7 days since a few microseconds elapsed between `now`
    # and the moment `last_pull_date` is generated
    assert (now - connector.last_pull_date).days == 7


def test_run(connector, freezer, event):
    def sleeper(_):
        sleep(0.1)

    with (
        patch.object(connector, "activate_subscriptions") as activate_subscriptions,
        patch.object(connector, "pull_content", return_value=event) as pull_content,
        patch.object(connector, "forward_events") as forward_events,
        patch.object(FORWARD_EVENTS_DURATION, "labels") as prometheus_labels,
    ):
        with patch("office365.management_api.connector.sleep") as sleep2:
            sleep2.side_effect = sleeper
            t = threading.Thread(target=connector.run)
            t.start()
            sleep(0.1)
            connector.stop()
            t.join()

        activate_subscriptions.assert_called_once()
        pull_content.assert_called_once_with(datetime.now(tz=UTC), datetime.now(tz=UTC))
        forward_events.assert_called_once_with(event)
        prometheus_labels.assert_called_once_with(
            intake_key=connector.configuration.intake_key, datasource="office365"
        )
