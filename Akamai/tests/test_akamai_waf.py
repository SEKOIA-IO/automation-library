from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests
import requests_mock
from freezegun import freeze_time

from akamai_modules import AkamaiModule
from akamai_modules.connector_akamai_waf import AkamaiWAFLogsConnector


@pytest.fixture
def fake_time():
    yield datetime(2025, 4, 1, 11, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def trigger(data_storage, fake_time):
    module = AkamaiModule()
    module.configuration = {
        "host": "example.com",
        "client_token": "1",
        "client_secret": "2",
        "access_token": "3",
    }

    with freeze_time(fake_time):
        trigger = AkamaiWAFLogsConnector(module=module, data_path=data_storage)

    trigger.configuration = {"config_id": 1, "intake_key": "intake_key", "frequency": 60, "page_size": 2000}

    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()

    yield trigger


@pytest.fixture
def raw_event():
    return {
        "attackData": {
            "clientIP": "192.0.2.82",
            "configId": "14227",
            "policyId": "qik1_26545",
            "ruleActions": "YWxlcnQ%3d%3bYWxlcnQ%3d%3bZGVueQ%3d%3d",
            "ruleData": "dGVsbmV0LmV4ZQ%3d%3d%3bdGVsbmV0LmV4ZQ%3d%3d%3bVmVjdG9yIFNjb3JlOiAxMCwgREVOWSB0aHJlc2hvbGQ6IDksIEFsZXJ0IFJ1bGVzOiA5NTAwMDI6OTUwMDA2LCBEZW55IFJ1bGU6ICwgTGFzdCBNYXRjaGVkIE1lc3NhZ2U6IFN5c3RlbSBDb21tYW5kIEluamVjdGlvbg%3d%3d",
            "ruleMessages": "U3lzdGVtIENvbW1hbmQgQWNjZXNz%3bU3lzdGVtIENvbW1hbmQgSW5qZWN0aW9u%3bQW5vbWFseSBTY29yZSBFeGNlZWRlZCBmb3IgQ29tbWFuZCBJbmplY3Rpb24%3d",
            "ruleSelectors": "QVJHUzpvcHRpb24%3d%3bQVJHUzpvcHRpb24%3d%3b",
            "ruleTags": "T1dBU1BfQ1JTL1dFQl9BVFRBQ0svRklMRV9JTkpFQ1RJT04%3d%3bT1dBU1BfQ1JTL1dFQl9BVFRBQ0svQ09NTUFORF9JTkpFQ1RJT04%3d%3bQUtBTUFJL1BPTElDWS9DTURfSU5KRUNUSU9OX0FOT01BTFk%3d",
            "ruleVersions": "NA%3d%3d%3bNA%3d%3d%3bMQ%3d%3d",
            "rules": "OTUwMDAy%3bOTUwMDA2%3bQ01ELUlOSkVDVElPTi1BTk9NQUxZ",
        },
        "botData": {"botScore": "100", "responseSegment": "3"},
        "clientData": {
            "appBundleId": "com.mydomain.myapp",
            "appVersion": "1.23",
            "sdkVersion": "4.7.1",
            "telemetryType": "2",
        },
        "format": "json",
        "geo": {"asn": "14618", "city": "ASHBURN", "continent": "288", "country": "US", "regionCode": "VA"},
        "httpMessage": {
            "bytes": "266",
            "host": "www.hmapi.com",
            "method": "GET",
            "path": "/",
            "port": "80",
            "protocol": "HTTP/1.1",
            "query": "option=com_jce%20telnet.exe",
            "requestHeaders": "User-Agent%3a%20BOT%2f0.1%20(BOT%20for%20JCE)%0d%0aAccept%3a%20text%2fhtml,application%2fxhtml+xml,application%2fxml%3bq%3d0.9,*%2f*%3bq%3d0.8%0d%0auniqueID%3a%20CR_H8%0d%0aAccept-Language%3a%20en-US,en%3bq%3d0.5%0d%0aAccept-Encoding%3a%20gzip,%20deflate%0d%0aConnection%3a%20keep-alive%0d%0aHost%3a%20www.hmapi.com%0d%0aContent-Length%3a%200%0d%0a",
            "requestId": "1158db1758e37bfe67b7c09",
            "responseHeaders": "Server%3a%20AkamaiGHost%0d%0aMime-Version%3a%201.0%0d%0aContent-Type%3a%20text%2fhtml%0d%0aContent-Length%3a%20266%0d%0aExpires%3a%20Tue,%2004%20Apr%202017%2010%3a57%3a02%20GMT%0d%0aDate%3a%20Tue,%2004%20Apr%202017%2010%3a57%3a02%20GMT%0d%0aConnection%3a%20close%0d%0aSet-Cookie%3a%20ak_bmsc%3dAFE4B6D8CEEDBD286FB10F37AC7B256617DB580D417F0000FE7BE3580429E23D%7epluPrgNmaBdJqOLZFwxqQLSkGGMy4zGMNXrpRIc1Md4qtsDfgjLCojg1hs2HC8JqaaB97QwQRR3YS1ulk+6e9Dbto0YASJAM909Ujbo6Qfyh1XpG0MniBzVbPMUV8oKhBLLPVSNCp0xXMnH8iXGZUHlUsHqWONt3+EGSbWUU320h4GKiGCJkig5r+hc6V1pi3tt7u3LglG3DloEilchdo8D7iu4lrvvAEzyYQI8Hao8M0%3d%3b%20expires%3dTue,%2004%20Apr%202017%2012%3a57%3a02%20GMT%3b%20max-age%3d7200%3b%20path%3d%2f%3b%20domain%3d.hmapi.com%3b%20HttpOnly%0d%0a",
            "start": "1491303422",
            "status": "200",
        },
        "type": "akamai_siem",
        "userRiskData": {
            "allow": "0",
            "general": "duc_1h:10|duc_1d:30",
            "originUserId": "jsmith007",
            "risk": "udfp:1325gdg4g4343g/M|unp:74256/H",
            "score": "75",
            "status": "0",
            "trust": "ugp:US",
            "username": "jsmith@example.com",
            "uuid": "964d54b7-0821-413a-a4d6-8131770ec8d5",
        },
        "version": "1.0",
    }


@pytest.fixture
def response_1() -> bytes:
    return b"""{"type": "akamai_siem", "format": "json", "version": 1.0, "attackData": {}, "httpMessage": {"requestId": 1, "start": "1743505200"}}\n
            {"type": "akamai_siem", "format": "json", "version": 1.0, "attackData": {}, "httpMessage": {"requestId": 1, "start": "1743505200"}}\n
            {"type": "akamai_siem", "format": "json", "version": 1.0, "attackData": {}, "httpMessage": {"requestId": 1, "start": "1743505200"}}\n
            {"total": 3, "offset": "OFFSET_TOKEN"}\n"""


@pytest.fixture
def response_2() -> bytes:
    return b"""{"total": 0, "offset": "EMPTY_TOKEN"}\n"""


def test_extract_attack_data(trigger, raw_event):
    attack_data = trigger.extract_attack_data(raw_event)

    assert attack_data == {
        "clientIP": "192.0.2.82",
        "configId": "14227",
        "policyId": "qik1_26545",
        "rules": [
            {
                "rule": "950002",
                "ruleAction": "alert",
                "ruleData": "telnet.exe",
                "ruleMessage": "System Command Access",
                "ruleSelector": "ARGS:option",
                "ruleTag": "OWASP_CRS/WEB_ATTACK/FILE_INJECTION",
                "ruleVersion": "4",
            },
            {
                "rule": "950006",
                "ruleAction": "alert",
                "ruleData": "telnet.exe",
                "ruleMessage": "System Command Injection",
                "ruleSelector": "ARGS:option",
                "ruleTag": "OWASP_CRS/WEB_ATTACK/COMMAND_INJECTION",
                "ruleVersion": "4",
            },
            {
                "rule": "CMD-INJECTION-ANOMALY",
                "ruleAction": "deny",
                "ruleData": "Vector Score: 10, DENY threshold: 9, Alert Rules: 950002:950006, Deny Rule: , Last Matched Message: System Command Injection",
                "ruleMessage": "Anomaly Score Exceeded for Command Injection",
                "ruleSelector": "",
                "ruleTag": "AKAMAI/POLICY/CMD_INJECTION_ANOMALY",
                "ruleVersion": "1",
            },
        ],
    }


def test_fetch_events(trigger, response_1, response_2):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=2000",
            status_code=200,
            content=response_1,
        )

        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=2000",
            status_code=200,
            content=response_2,
        )

        events = list(trigger.fetch_events())
        assert events == [
            [
                {
                    "type": "akamai_siem",
                    "format": "json",
                    "version": 1.0,
                    "attackData": {},
                    "httpMessage": {"requestId": 1, "start": "1743505200"},
                },
                {
                    "type": "akamai_siem",
                    "format": "json",
                    "version": 1.0,
                    "attackData": {},
                    "httpMessage": {"requestId": 1, "start": "1743505200"},
                },
                {
                    "type": "akamai_siem",
                    "format": "json",
                    "version": 1.0,
                    "attackData": {},
                    "httpMessage": {"requestId": 1, "start": "1743505200"},
                },
            ]
        ]


def test_request_error(trigger):
    msg = {
        "clientIp": "192.0.2.201",
        "detail": "Internal server error",
        "instance": "https://akab-1234abcd.luna.akamaiapis.net/siem/v1/configs=12345?offset=123",
        "method": "GET",
        "requestId": "9ab12ef",
        "requestTime": "2023-06-20T15:02:30Z",
        "serverIp": "192.0.2.221",
        "title": "Error",
        "type": "https://problems.cloudsecurity.akamaiapis.net/siem/v1/error",
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=2000", status_code=500, json=msg
        )

        with pytest.raises(requests.HTTPError):
            trigger.next_batch()


def test_next_batch_sleep_until_next_round(trigger, response_1, response_2):
    with patch("akamai_modules.connector_akamai_waf.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=2000",
            status_code=200,
            content=response_1,
        )

        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=2000",
            status_code=200,
            content=response_2,
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_long_next_batch_should_not_sleep(trigger, response_1, response_2):
    with patch("akamai_modules.connector_akamai_waf.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=2000",
            status_code=200,
            content=response_1,
        )

        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=2000",
            status_code=200,
            content=response_2,
        )

        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0
