import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests_mock

from proofpoint_modules.trigger_tap_events import RFC3339_STRICT_FORMAT, TAPEventsTrigger


@pytest.fixture
def trigger(symphony_storage):
    trigger = TAPEventsTrigger(data_path=symphony_storage)
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


def test_get_next_events(trigger):
    url = f"{trigger.configuration.api_host}/v2/siem/all"
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
            "queryEndTime": "2016-06-24T21:36:00Z",
        }
        # flake8: qa

        mock.get(url, json=reponse)
        trigger.forward_next_batch()
        assert trigger.last_retrieval_date == datetime(2016, 6, 24, 21, 36, tzinfo=timezone.utc)
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
