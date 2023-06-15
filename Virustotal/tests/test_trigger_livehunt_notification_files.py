import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

import pytest
import requests_mock

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
