import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest
import requests_mock

from proofpoint_modules.trigger_tap_events import RFC3339_STRICT_FORMAT, TAPEventsTrigger

TAP_URL = "https://tap-api-v2.proofpoint.com/v2/siem/all"


def build_trigger(data_path):
    trigger = TAPEventsTrigger(data_path=data_path)
    trigger.module.configuration = {}
    trigger.configuration = {
        "frequency": 60,
        "chunk_size": 1,
        "api_host": "https://tap-api-v2.proofpoint.com",
        "client_principal": "my-id",
        "client_secret": "my-password",
        "intake_key": "foo",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def trigger(symphony_storage):
    return build_trigger(symphony_storage)


def to_api_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def save_checkpoint(data_path, dt: datetime) -> None:
    (data_path / "context.json").write_text(json.dumps({"most_recent_date_seen": dt.isoformat()}))


def read_checkpoint(data_path) -> datetime | None:
    context = data_path / "context.json"
    if not context.exists():
        return None
    value = json.loads(context.read_text()).get("most_recent_date_seen")
    return datetime.fromisoformat(value) if value else None


def requested_since_time(mock) -> datetime:
    since_time = parse_qs(urlparse(mock.last_request.url).query)["sinceTime"][0]
    return datetime.strptime(since_time, RFC3339_STRICT_FORMAT).replace(tzinfo=timezone.utc)


def api_response(query_end_time: datetime) -> dict:
    return {
        "messagesDelivered": [{"GUID": "delivered-1", "messageTime": to_api_date(query_end_time)}],
        "clicksBlocked": [{"GUID": "click-1", "clickTime": to_api_date(query_end_time)}],
        "queryEndTime": to_api_date(query_end_time),
    }


def test_get_next_events(trigger):
    url = f"{trigger.configuration.api_host}/v2/siem/all"
    query_end_time = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=30)
    with requests_mock.Mocker() as mock:
        # flake8: noqa
        reponse = {
            "clicksPermitted": [
                {
                    "campaignId": "46e01b8a-c899-404d-bcd9-189bb393d1a7",
                    "classification": "MALWARE",
                    "clickIP": "192.0.2.1",
                    "clickTime": "2016-06-24T19:17:44.000Z",
                    "GUID": "b27dbea0-87d5-463b-b93c-4e8b708289ce",
                    "id": "8c8b4895-a277-449f-r797-547e3c89b25a",
                    "messageID": "8c6cfedd-3050-4d65-8c09-c5f65c38da81",
                    "recipient": "bruce.wayne@pharmtech.zz",
                    "sender": "9facbf452def2d7efc5b5c48cdb837fa@badguy.zz",
                    "senderIP": "192.0.2.255",
                    "threatID": "61f7622167144dba5e3ae4480eeee78b23d66f7dfed970cfc3d086cc0dabdf50",
                    "threatTime": "2016-06-24T19:17:46.000Z",
                    "threatURL": "https://threatinsight.proofpoint.com/#/73aa0499-dfc8-75eb-1de8-a471b24a2e75/threat/u/61f7622167144dba5e3ae4480eeee78b23d66f7dfed970cfc3d086cc0dabdf50",
                    "threatStatus": "active",
                    "url": "http://badguy.zz/",
                    "userAgent": "Mozilla/5.0(WindowsNT6.1;WOW64;rv:27.0)Gecko/20100101Firefox/27.0",
                }
            ],
            "messagesBlocked": [
                {
                    "GUID": "c26dbea0-80d5-463b-b93c-4e8b708219ce",
                    "QID": "r2FNwRHF004109",
                    "ccAddresses": ["bruce.wayne@university-of-education.zz"],
                    "clusterId": "pharmtech_hosted",
                    "completelyRewritten": "true",
                    "fromAddress": "badguy@evil.zz",
                    "headerCC": '"Bruce Wayne" <bruce.wayne@university-of-education.zz>',
                    "headerFrom": '"A. Badguy" <badguy@evil.zz>',
                    "headerReplyTo": None,
                    "headerTo": '"Clark Kent" <clark.kent@pharmtech.zz>; "Diana Prince" <diana.prince@pharmtech.zz>',
                    "impostorScore": 0,
                    "malwareScore": 100,
                    "messageID": "20160624211145.62086.mail@evil.zz",
                    "messageParts": [
                        {
                            "contentType": "text/plain",
                            "disposition": "inline",
                            "filename": "text.txt",
                            "md5": "008c5926ca861023c1d2a36653fd88e2",
                            "oContentType": "text/plain",
                            "sandboxStatus": "unsupported",
                            "sha256": "85738f8f9a7f1b04b5329c590ebcb9e425925c6d0984089c43a022de4f19c281",
                        },
                        {
                            "contentType": "application/pdf",
                            "disposition": "attached",
                            "filename": "Invoice for Pharmtech.pdf",
                            "md5": "5873c7d37608e0d49bcaa6f32b6c731f",
                            "oContentType": "application/pdf",
                            "sandboxStatus": "threat",
                            "sha256": "2fab740f143fc1aa4c1cd0146d334c5593b1428f6d062b2c406e5efe8abe95ca",
                        },
                    ],
                    "messageTime": "2016-06-24T21:18:38.000Z",
                    "modulesRun": ["pdr", "sandbox", "spam", "urldefense"],
                    "phishScore": 46,
                    "policyRoutes": ["default_inbound", "executives"],
                    "quarantineFolder": "Attachment Defense",
                    "quarantineRule": "module.sandbox.threat",
                    "recipient": [
                        "clark.kent@pharmtech.zz",
                        "diana.prince@pharmtech.zz",
                    ],
                    "replyToAddress": None,
                    "sender": "e99d7ed5580193f36a51f597bc2c0210@evil.zz",
                    "senderIP": "192.0.2.255",
                    "spamScore": 4,
                    "subject": "Please find a totally safe invoice attached.",
                    "threatsInfoMap": [
                        {
                            "campaignId": "46e01b8a-c899-404d-bcd9-189bb393d1a7",
                            "classification": "MALWARE",
                            "threat": "2fab740f143fc1aa4c1cd0146d334c5593b1428f6d062b2c406e5efe8abe95ca",
                            "threatId": "2fab740f143fc1aa4c1cd0146d334c5593b1428f6d062b2c406e5efe8abe95ca",
                            "threatStatus": "active",
                            "threatTime": "2016-06-24T21:18:38.000Z",
                            "threatType": "ATTACHMENT",
                            "threatUrl": "https://threatinsight.proofpoint.com/#/73aa0499-dfc8-75eb-1de8-a471b24a2e75/threat/u/2fab740f143fc1aa4c1cd0146d334c5593b1428f6d062b2c406e5efe8abe95ca",
                        },
                        {
                            "campaignId": "46e01b8a-c899-404d-bcd9-189bb393d1a7",
                            "classification": "MALWARE",
                            "threat": "badsite.zz",
                            "threatId": "3ba97fc852c66a7ba761450edfdfb9f4ffab74715b591294f78b5e37a76481aa",
                            "threatTime": "2016-06-24T21:18:07.000Z",
                            "threatType": "URL",
                            "threatUrl": "https://threatinsight.proofpoint.com/#/73aa0499-dfc8-75eb-1de8-a471b24a2e75/threat/u/3ba97fc852c66a7ba761450edfdfb9f4ffab74715b591294f78b5e37a76481aa",
                        },
                    ],
                    "toAddresses": [
                        "clark.kent@pharmtech.zz",
                        "diana.prince@pharmtech.zz",
                    ],
                    "xmailer": "Spambot v2.5",
                },
            ],
            "queryEndTime": to_api_date(query_end_time),
        }
        # flake8: qa

        mock.get(url, json=reponse)
        trigger.forward_next_batch()
        assert trigger.last_retrieval_date == query_end_time
        assert read_checkpoint(trigger.data_path) == query_end_time
        assert trigger.push_events_to_intakes.called
        records = trigger.push_events_to_intakes.call_args_list[0].kwargs.get("events", [])
        assert len(records) == 2
        assert all([isinstance(record, str) for record in records])


@pytest.mark.skipif("{'PROOFPOINT_PRINCIPAL', 'PROOFPOINT_SECRET'}.issubset(os.environ.keys()) == False")
def test_forward_next_batches_integration(symphony_storage):
    trigger = TAPEventsTrigger(data_path=symphony_storage)
    trigger.module.configuration = {}
    trigger.configuration = {
        "frequency": 60,
        "chunk_size": 1,
        "api_host": "https://tap-api-v2.proofpoint.com",
        "client_principal": os.environ["PROOFPOINT_PRINCIPAL"],
        "client_secret": os.environ["PROOFPOINT_SECRET"],
        "intake_key": "foo",
    }
    trigger.last_retrieval_date = datetime.now(timezone.utc) - timedelta(hours=3)
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    trigger.forward_next_batch()
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0


def test_first_run_starts_five_minutes_ago(trigger):
    now = datetime.now(timezone.utc)
    with requests_mock.Mocker() as mock:
        mock.get(TAP_URL, json=api_response(now))
        trigger.forward_next_batch()

    since_time = requested_since_time(mock)
    assert now - timedelta(minutes=5, seconds=5) <= since_time <= now - timedelta(minutes=4, seconds=55)


def test_resume_from_saved_checkpoint_after_restart(symphony_storage):
    # the connector was down for 20 minutes: it must resume from the saved checkpoint, not from now - 5 minutes
    saved = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=20)
    save_checkpoint(symphony_storage, saved)
    trigger = build_trigger(symphony_storage)

    query_end_time = datetime.now(timezone.utc).replace(microsecond=0)
    with requests_mock.Mocker() as mock:
        mock.get(TAP_URL, json=api_response(query_end_time))
        trigger.forward_next_batch()

    assert requested_since_time(mock) == saved
    assert read_checkpoint(symphony_storage) == query_end_time


def test_new_instance_reads_checkpoint_written_by_previous_one(symphony_storage):
    first = build_trigger(symphony_storage)
    query_end_time = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=10)
    with requests_mock.Mocker() as mock:
        mock.get(TAP_URL, json=api_response(query_end_time))
        first.forward_next_batch()

    # restart: a brand new instance on the same data path
    second = build_trigger(symphony_storage)
    with requests_mock.Mocker() as mock:
        mock.get(TAP_URL, json=api_response(datetime.now(timezone.utc)))
        second.forward_next_batch()

    assert requested_since_time(mock) == query_end_time


def test_checkpoint_not_advanced_when_push_fails(symphony_storage):
    saved = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)
    save_checkpoint(symphony_storage, saved)
    trigger = build_trigger(symphony_storage)
    trigger.push_events_to_intakes.side_effect = Exception("intake unavailable")

    with requests_mock.Mocker() as mock:
        mock.get(TAP_URL, json=api_response(datetime.now(timezone.utc)))
        with pytest.raises(Exception, match="intake unavailable"):
            trigger.forward_next_batch()

    assert read_checkpoint(symphony_storage) == saved
    assert trigger.last_retrieval_date == saved

    # the next attempt retries the same window
    trigger.push_events_to_intakes.side_effect = None
    with requests_mock.Mocker() as mock:
        mock.get(TAP_URL, json=api_response(datetime.now(timezone.utc)))
        trigger.forward_next_batch()
    assert requested_since_time(mock) == saved


@pytest.mark.parametrize("status_code", [401, 429, 500])
def test_checkpoint_not_advanced_when_api_fails(symphony_storage, status_code):
    saved = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)
    save_checkpoint(symphony_storage, saved)
    trigger = build_trigger(symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(TAP_URL, status_code=status_code)
        trigger.forward_next_batch()

    assert not trigger.push_events_to_intakes.called
    assert read_checkpoint(symphony_storage) == saved
    assert trigger.last_retrieval_date == saved


def test_checkpoint_advanced_when_no_events(symphony_storage):
    saved = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)
    save_checkpoint(symphony_storage, saved)
    trigger = build_trigger(symphony_storage)

    query_end_time = datetime.now(timezone.utc).replace(microsecond=0)
    with requests_mock.Mocker() as mock:
        mock.get(TAP_URL, json={"queryEndTime": to_api_date(query_end_time)})
        trigger.forward_next_batch()

    assert not trigger.push_events_to_intakes.called
    assert read_checkpoint(symphony_storage) == query_end_time


def test_since_time_capped_to_one_hour(symphony_storage):
    # the API does not accept a sinceTime older than one hour
    save_checkpoint(symphony_storage, datetime.now(timezone.utc) - timedelta(hours=3))
    trigger = build_trigger(symphony_storage)

    now = datetime.now(timezone.utc)
    with requests_mock.Mocker() as mock:
        mock.get(TAP_URL, json=api_response(now))
        trigger.forward_next_batch()

    since_time = requested_since_time(mock)
    assert now - timedelta(hours=1, seconds=5) <= since_time <= now - timedelta(minutes=59, seconds=55)
