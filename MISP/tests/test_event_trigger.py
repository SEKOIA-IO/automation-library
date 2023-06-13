from datetime import datetime
from unittest.mock import patch

import pytest
from freezegun import freeze_time
from misp.trigger import MISPTrigger


@pytest.fixture
def misp_api(misp_event, requests_mock, misp_base_server, misp_base_url: str):
    requests_mock.post(misp_base_url + "events/restSearch", json=[misp_event])
    yield requests_mock


@pytest.fixture
def misp_trigger(misp_api, misp_base_url):
    trigger = MISPTrigger()

    trigger.module.configuration = {
        "misp_url": misp_base_url,
        "misp_api_key": "fake_api_key",
    }
    trigger.configuration = {}

    return trigger


@patch.object(MISPTrigger, "send_event")
def test_misp_trigger(send_event_mock, misp_trigger, misp_event):
    misp_trigger._run(datetime.now().timestamp())
    send_event_mock.assert_called_with("Daily Incremental Cryptolaemus Emotet IOCs (payload)", {"event": misp_event})


def test_misp_trigger_sleep_time():
    trigger = MISPTrigger()

    trigger.configuration = {}
    assert trigger.sleep_time == 60

    trigger.configuration = {"sleep_time": 5}
    assert trigger.sleep_time == 5


@freeze_time("2019-06-19 23:00:00")
@patch.object(MISPTrigger, "send_event")
def test_misp_trigger_attribute_filter(send_event_mock, misp_trigger, misp_event):
    misp_trigger.configuration = {"attributes_filter": "86400"}

    misp_trigger._run(datetime.now().timestamp())
    name, event = send_event_mock.call_args[0]

    # Old attributes should be filtered out,
    # but context attributes should be kept
    assert len(event["event"]["Event"]["Attribute"]) == 10

    found_external_analysis = False
    for attribute in event["event"]["Event"]["Attribute"]:
        if attribute["category"] == "External analysis":
            found_external_analysis = True

    assert found_external_analysis is True


@patch.object(MISPTrigger, "send_event")
def test_misp_trigger_attribute_filter_do_not_send_event(send_event_mock, misp_trigger, misp_event):
    # This test is not faking the date, so all attributes should be filtered out
    # An event with no new attribute should not trigger a playbook run
    misp_trigger.configuration = {"attributes_filter": "86400"}

    misp_trigger._run(datetime.now().timestamp())
    send_event_mock.assert_not_called()


@freeze_time("2019-06-19 23:00:00")
@patch.object(MISPTrigger, "send_event")
def test_misp_trigger_attribute_filter_cache(send_event_mock, misp_trigger, misp_event):
    misp_trigger.configuration = {"attributes_filter": "86400"}

    # Fetch MISP updates, this should create an event
    misp_trigger._run(datetime.now().timestamp())
    assert send_event_mock.call_count == 1

    # Fetch MISP updates another time with same events, this should not create another event
    misp_trigger._old_ids = []
    misp_trigger._run(datetime.now().timestamp())
    assert send_event_mock.call_count == 1
