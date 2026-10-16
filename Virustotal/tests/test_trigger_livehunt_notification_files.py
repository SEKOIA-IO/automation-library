import copy
import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

import pytest
import requests
import requests_mock
from sekoia_automation.exceptions import SendEventError

from virustotal.livehunt_notification_files_trigger import LivehuntNotificationFilesTrigger


@pytest.fixture(autouse=True)
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


@pytest.fixture
def livehunt_response():
    with open(os.path.join(os.path.dirname(__file__), "data", "livehunt_response.json")) as f:
        return json.load(f)


@contextmanager
def mock_vtapi(json_response):
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://www.virustotal.com/api/v3/intelligence/hunting_notification_files",
            json=json_response,
        )

        mock.get(
            "https://www.virustotal.com/api/v3/intelligence/hunting_notification_files?cursor=fake_cursor",
            json={"data": []},
        )

        yield mock


@pytest.fixture
def trigger(symphony_storage):
    trigger = LivehuntNotificationFilesTrigger(data_path=symphony_storage)

    trigger.module.configuration = {"apikey": "fake_api_key"}
    trigger.configuration = {}

    return trigger


def get_name_event_and_notification(storage, send_event):
    (name, event, directory), kwargs = send_event.call_args

    assert kwargs == {"remove_directory": True}

    with storage.joinpath(directory).joinpath(event["notification_path"]).open("r") as fd:
        return name, event, json.load(fd)


@patch.object(LivehuntNotificationFilesTrigger, "send_event")
def test_trigger_results(send_event, symphony_storage, trigger, livehunt_response):
    with mock_vtapi(livehunt_response):
        trigger.get_new_notifications()

    send_event.assert_called_once()
    name, event, notification = get_name_event_and_notification(symphony_storage, send_event)

    assert name == (
        "MARITIME / maritime_spam_keywords / " "6483f16eabe91a1615274f8fc24cb4421f4e77f867c6d8c43aed2c412c31dd1b"
    )

    assert event["md5"] == "9c690e200b2b4e155dcf54bf2afb9506"
    assert event["sha1"] == "5ccab7eca67a56c556fd0ce83713d3a37450bbd1"
    assert event["sha256"] == "6483f16eabe91a1615274f8fc24cb4421f4e77f867c6d8c43aed2c412c31dd1b"
    assert event["name"] == "classes.dex"
    assert event["ruleset_name"] == "MARITIME"
    assert event["rule_name"] == "maritime_spam_keywords"
    assert event["notification_id"] == "1061070168115286-6380064847626240-505cd972e9b5a4207d1656802eae0377"
    assert event["notification_date"] == 1584978493

    assert notification["attributes"]["exiftool"]["FileType"] == "DEX"


@patch.object(LivehuntNotificationFilesTrigger, "send_event")
def test_trigger_cache(send_event, symphony_storage, trigger, livehunt_response):
    with mock_vtapi(livehunt_response):
        # Get new notifications, it should generate 1 event
        trigger.get_new_notifications()
        send_event.assert_called_once()

        # Get new notifications once more, it should not generate a new event
        trigger.get_new_notifications()
        send_event.assert_called_once()


@patch.object(LivehuntNotificationFilesTrigger, "send_event")
def test_skip_history(send_event, symphony_storage, trigger, livehunt_response):
    trigger.configuration = {"skip_history": True}

    # Get new notifications. The first run should ignore events
    with mock_vtapi(livehunt_response):
        trigger.get_new_notifications()
        send_event.assert_not_called()

    # Create a fake notification
    response = copy.deepcopy(livehunt_response)
    notification = copy.deepcopy(response["data"][0])
    notification["context_attributes"]["notification_id"] = "fake_id"
    notification["context_attributes"]["notification_date"] += 1
    response["data"] = [notification, response["data"][0]]

    # Calling the trigger a second time should generate only 1 event
    with mock_vtapi(response):
        trigger.get_new_notifications()
        send_event.assert_called_once()


@patch.object(LivehuntNotificationFilesTrigger, "send_event")
def test_no_meaningful_name(send_event, symphony_storage, trigger, livehunt_response):
    # Create a fake notification with no meaningful name
    del livehunt_response["data"][0]["attributes"]["meaningful_name"]

    # Calling the trigger should generate an event without a name
    with mock_vtapi(livehunt_response):
        trigger.get_new_notifications()
        send_event.assert_called_once()

    _, event, _ = get_name_event_and_notification(symphony_storage, send_event)
    assert "name" not in event


class StopTrigger(Exception):
    pass


def test_sleep_time_defaults_to_300(trigger):
    assert trigger.sleep_time == 300


def test_sleep_time_from_configuration(trigger):
    trigger.configuration = {"sleep_time": "60"}

    assert trigger.sleep_time == 60


def test_run_keeps_polling_after_errors(trigger, monkeypatch, caplog):
    outcomes = iter([None, SendEventError("failed to send"), ValueError("boom")])

    def get_new_notifications():
        outcome = next(outcomes)
        if outcome is not None:
            raise outcome

    sleeps: list[float] = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise StopTrigger()

    trigger.configuration = {"sleep_time": 10}
    monkeypatch.setattr(trigger, "get_new_notifications", get_new_notifications)
    monkeypatch.setattr("virustotal.livehunt_notification_files_trigger.time.sleep", sleep)

    with caplog.at_level(logging.ERROR), pytest.raises(StopTrigger):
        trigger.run()

    assert sleeps == [10, 10, 10]
    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "ValueError: boom" in errors[0].getMessage()


def test_get_notifications_raises_on_http_error(trigger, requests_mock):
    requests_mock.get(
        "https://www.virustotal.com/api/v3/intelligence/hunting_notification_files",
        status_code=401,
    )

    with pytest.raises(requests.HTTPError):
        trigger.get_notifications()

    assert requests_mock.last_request.headers["x-apikey"] == "fake_api_key"


@patch.object(LivehuntNotificationFilesTrigger, "send_event")
def test_get_new_notifications_without_data(send_event, trigger, requests_mock):
    requests_mock.get(
        "https://www.virustotal.com/api/v3/intelligence/hunting_notification_files",
        json={"data": [], "meta": {}},
    )

    trigger.get_new_notifications()

    send_event.assert_not_called()
    assert requests_mock.call_count == 1


@patch.object(LivehuntNotificationFilesTrigger, "send_event")
def test_get_new_notifications_stops_at_older_notification(send_event, trigger, livehunt_response):
    with mock_vtapi(livehunt_response):
        trigger.get_new_notifications()
    send_event.assert_called_once()

    newer = copy.deepcopy(livehunt_response["data"][0])
    newer["context_attributes"]["notification_id"] = "newer_id"
    newer["context_attributes"]["notification_date"] += 10
    older = copy.deepcopy(livehunt_response["data"][0])
    older["context_attributes"]["notification_id"] = "older_id"
    older["context_attributes"]["notification_date"] -= 10
    response = {"data": [newer, older], "meta": {}}

    send_event.reset_mock()
    with mock_vtapi(response):
        trigger.get_new_notifications()

    send_event.assert_called_once()
    _, event, _ = send_event.call_args.args
    assert event["notification_id"] == "newer_id"
