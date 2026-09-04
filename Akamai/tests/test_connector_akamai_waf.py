from datetime import datetime, timezone
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
import requests
import requests_mock
from freezegun import freeze_time

from akamai_modules import AkamaiModule
from akamai_modules.connector_akamai_waf import AkamaiWAFLogsConnector, AkamaiWAFLogsConnectorConfiguration
from akamai_modules.models import AkamaiModuleConfiguration


@pytest.fixture
def fake_time():
    yield datetime(2025, 4, 1, 11, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def trigger(data_storage, fake_time):
    module = AkamaiModule()
    module.configuration = AkamaiModuleConfiguration(
        host="example.com",
        client_token="1",
        client_secret="2",
        access_token="3",
    )

    with freeze_time(fake_time):
        trigger = AkamaiWAFLogsConnector(module=module, data_path=data_storage)

    trigger.configuration = AkamaiWAFLogsConnectorConfiguration(
        config_id="1",
        intake_key="intake_key",
        frequency=60,
    )

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


def make_response_with_n_events(n: int, offset_token: str = "OFFSET_TOKEN") -> bytes:
    lines = []
    for i in range(n):
        lines.append(
            f'{{"type": "akamai_siem", "format": "json", "version": 1.0, '
            f'"attackData": {{}}, "httpMessage": {{"requestId": {i}, "start": "1743505200"}}}}'
        )
    lines.append(f'{{"total": {n}, "offset": "{offset_token}"}}')
    return ("\n".join(lines) + "\n").encode()


def make_truncated_response_with_n_events(n: int) -> bytes:
    """Build a response that contains n events but no trailing context/offset line,
    simulating a truncated or malformed API stream."""
    lines = []
    for i in range(n):
        lines.append(
            f'{{"type": "akamai_siem", "format": "json", "version": 1.0, '
            f'"attackData": {{}}, "httpMessage": {{"requestId": {i}, "start": "1743505200"}}}}'
        )
    return ("\n".join(lines) + "\n").encode()


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


def test_process_event_ignores_malformed_headers(trigger, raw_event):
    event = raw_event.copy()
    event["httpMessage"] = raw_event["httpMessage"].copy()
    event["httpMessage"]["responseHeaders"] = (
        "Content-Type%3A%20application%2Fjson%0A"
        "malformed-header-line-without-separator%0A"
        "Server%3A%20AkamaiGHost"
    )

    trigger.process_event(event)

    assert event["httpMessage"]["responseHeaders"] == {
        "Content-Type": "application/json",
        "Server": "AkamaiGHost",
    }


@pytest.mark.parametrize(
    "encoded_headers,expected_headers",
    [
        (
            "X-Test%3A%201%0Ajust-text-without-colon%0AAnother-Test%3A%202",
            {"X-Test": "1", "Another-Test": "2"},
        ),
        (
            "X-Ok%3A%20ok%0A%3Avalue-with-empty-key%0AX-Other%3A%20other",
            {"X-Ok": "ok", "X-Other": "other"},
        ),
        (
            "\n\r\nX-One%3A%201\n\nX-Two%3A%202\r\n",
            {"X-One": "1", "X-Two": "2"},
        ),
    ],
)
def test_extract_headers_handles_multiple_malformed_line_patterns(trigger, encoded_headers, expected_headers):
    assert trigger.extract_headers(encoded_headers) == expected_headers


def test_process_event_logs_malformed_header_nature_with_raw_content(trigger, raw_event):
    event = raw_event.copy()
    event["httpMessage"] = raw_event["httpMessage"].copy()
    event["httpMessage"]["requestHeaders"] = "Auth%3A%20token%0Amalformed-sensitive-line-user%3Dalice"
    event["httpMessage"]["responseHeaders"] = "%3Ano-key%0AContent-Type%3A%20application%2Fjson"

    trigger.process_event(event)

    trigger.log.assert_called_once()
    _, kwargs = trigger.log.call_args

    assert kwargs["level"] == "warning"
    message = kwargs["message"]
    assert "request_header_lines_ignored=1" in message
    assert "response_header_lines_ignored=1" in message
    assert "request_malformed_reasons={'missing_separator': 1}" in message
    assert "response_malformed_reasons={'empty_key': 1}" in message
    assert "raw_request_headers=" in message
    assert "malformed-sensitive-line-user%3Dalice" in message
    assert "raw_response_headers=" in message
    assert "raw_event=" in message


def test_process_event_logs_invalid_header_type(trigger, raw_event):
    event = raw_event.copy()
    event["httpMessage"] = raw_event["httpMessage"].copy()
    event["httpMessage"]["requestHeaders"] = ["not-a-string"]

    trigger.process_event(event)

    trigger.log.assert_called_once()
    _, kwargs = trigger.log.call_args

    assert kwargs["level"] == "warning"
    message = kwargs["message"]
    assert "request_header_lines_ignored=1" in message
    assert "request_malformed_reasons={'invalid_type': 1}" in message


def test_process_event_handles_non_dict_http_message(trigger, raw_event):
    event = raw_event.copy()
    event["httpMessage"] = None

    trigger.process_event(event)

    assert event["httpMessage"] == {}
    assert isinstance(event["attackData"], dict)
    assert "rules" in event["attackData"]
    assert any(
        "Skipped httpMessage normalization because httpMessage is not a mapping" in call.kwargs.get("message", "")
        for call in trigger.log.call_args_list
    )
    assert any("raw_http_message=null" in call.kwargs.get("message", "") for call in trigger.log.call_args_list)


def test_fetch_events(trigger, response_1, response_2):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=response_1,
        )

        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
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
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000", status_code=500, json=msg
        )

        with pytest.raises(requests.HTTPError):
            trigger.next_batch()


@pytest.mark.parametrize(
    "batch_duration,expected_sleep_call_count",
    [
        (16, 1),
        ("longer_than_frequency", 0),
    ],
)
def test_next_batch_sleep_behavior(trigger, response_1, response_2, batch_duration, expected_sleep_call_count):
    with patch("akamai_modules.connector_akamai_waf.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=response_1,
        )

        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
            status_code=200,
            content=response_2,
        )

        effective_batch_duration = (
            trigger.configuration.frequency + 20 if batch_duration == "longer_than_frequency" else batch_duration
        )
        start_time = 1666711174.0
        end_time = start_time + effective_batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == expected_sleep_call_count


@pytest.mark.parametrize(
    "chunk_size_override,scenario,expected_chunk_lengths",
    [
        (10, "less_than_chunk_size", [9]),
        (None, "exactly_chunk_size", ["chunk"]),
        (None, "chunk_plus_remainder", ["chunk", 500]),
        (None, "multiple_full_chunks", ["chunk", "chunk", "chunk"]),
    ],
)
def test_fetch_events_chunking_patterns(trigger, response_2, chunk_size_override, scenario, expected_chunk_lengths):
    if chunk_size_override is not None:
        trigger.chunk_size = chunk_size_override

    if scenario == "less_than_chunk_size":
        n_events = trigger.chunk_size - 1
    elif scenario == "exactly_chunk_size":
        n_events = trigger.chunk_size
    elif scenario == "chunk_plus_remainder":
        n_events = trigger.chunk_size + 500
    elif scenario == "multiple_full_chunks":
        n_events = trigger.chunk_size * 3
    else:
        raise AssertionError(f"Unknown chunking scenario: {scenario}")

    big_response = make_response_with_n_events(n_events, offset_token="OFFSET_TOKEN")

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=big_response,
        )
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
            status_code=200,
            content=response_2,
        )

        chunks = list(trigger.fetch_events())

    expected_lengths = [trigger.chunk_size if length == "chunk" else length for length in expected_chunk_lengths]
    assert [len(chunk) for chunk in chunks] == expected_lengths
    assert sum(len(chunk) for chunk in chunks) == n_events


def test_chunk_size_limits_memory_per_yield(trigger, response_2):
    n_events = trigger.chunk_size * 2 + 300
    big_response = make_response_with_n_events(n_events, offset_token="OFFSET_TOKEN")

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=big_response,
        )
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
            status_code=200,
            content=response_2,
        )

        chunks = list(trigger.fetch_events())

    # The key invariant: memory is bounded per chunk
    for chunk in chunks:
        assert len(chunk) <= trigger.chunk_size

    # And no events are lost
    assert sum(len(c) for c in chunks) == n_events


@pytest.mark.parametrize(
    "n_events,expected_chunk_lengths",
    [
        (5, [5]),
        ("chunk_plus_300", ["chunk", 300]),
    ],
)
def test_fetch_events_truncated_response_yields_all_events(trigger, n_events, expected_chunk_lengths):
    """Return all events when the API stream ends without pagination context."""
    effective_n_events = trigger.chunk_size + 300 if n_events == "chunk_plus_300" else n_events
    truncated_response = make_truncated_response_with_n_events(effective_n_events)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=truncated_response,
        )

        chunks = list(trigger.fetch_events())

    expected_lengths = [trigger.chunk_size if length == "chunk" else length for length in expected_chunk_lengths]
    assert [len(chunk) for chunk in chunks] == expected_lengths
    assert sum(len(chunk) for chunk in chunks) == effective_n_events


def test_load_events_cache_restores_event_ids(trigger):
    @contextmanager
    def fake_context():
        yield {"events_cache": ["evt-1", "evt-2"]}

    trigger.cursor._context = fake_context()

    restored_cache = trigger.load_events_cache()

    assert restored_cache["evt-1"] is True
    assert restored_cache["evt-2"] is True


def test_fetch_events_logs_unchanged_checkpoint(trigger):
    with patch.object(trigger, "_AkamaiWAFLogsConnector__fetch_next_events", return_value=iter([[]])):
        chunks = list(trigger.fetch_events())

    assert chunks == []
    assert any("Kept checkpoint unchanged" in call.kwargs.get("message", "") for call in trigger.log.call_args_list)


def test_request_error_with_unparseable_body_logs_warning(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=500,
            text="this-is-not-json",
        )

        with pytest.raises(requests.HTTPError):
            trigger.next_batch()

    assert any(
        call.kwargs.get("level") == "warning"
        and "Failed to parse Akamai API error response body" in call.kwargs.get("message", "")
        for call in trigger.log.call_args_list
    )


def test_request_error_sanitizes_and_truncates_long_multiline_values(trigger):
    very_long_detail = "line1\nline2\t" + ("x" * 400)
    msg = {
        "clientIp": "192.0.2.201",
        "detail": very_long_detail,
        "instance": "https://example.com/path\nwith-newline",
        "method": "GET",
        "requestId": "9ab12ef",
        "requestTime": "2023-06-20T15:02:30Z",
        "serverIp": "192.0.2.221",
        "title": "Error\nTitle",
        "type": "https://problems.example.net/type",
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=500,
            json=msg,
        )

        with pytest.raises(requests.HTTPError):
            trigger.next_batch()

    payload_logs = [
        call.kwargs.get("message", "")
        for call in trigger.log.call_args_list
        if call.kwargs.get("level") == "error" and "error_payload=true" in call.kwargs.get("message", "")
    ]
    assert len(payload_logs) == 1

    payload_message = payload_logs[0]
    assert "\n" not in payload_message
    assert "\r" not in payload_message
    assert "\t" not in payload_message
    assert "api_error_detail=" in payload_message
    assert "..." in payload_message


@pytest.mark.parametrize(
    "stream,seed_duplicate_cache,expected_push_call_count,expected_log_fragment",
    [
        (
            make_response_with_n_events(1, offset_token="OFFSET_TOKEN"),
            True,
            0,
            "Skipped forwarding chunk because all events were duplicates",
        ),
        (
            (
                b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"start": "1743505200"}}\n'
                b'{"total": 1, "offset": "OFFSET_TOKEN"}\n'
            ),
            False,
            1,
            "Forwarded event with fallback deduplication because requestId is missing",
        ),
    ],
)
def test_next_batch_chunk_forwarding_decision(
    trigger, response_2, stream, seed_duplicate_cache, expected_push_call_count, expected_log_fragment
):
    if seed_duplicate_cache:
        trigger.events_cache[0] = True

    with patch("akamai_modules.connector_akamai_waf.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=stream,
        )
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
            status_code=200,
            content=response_2,
        )

        mock_time.time.side_effect = [1666711174.0, 1666711235.0]
        trigger.next_batch()

    assert trigger.push_events_to_intakes.call_count == expected_push_call_count
    assert any(expected_log_fragment in call.kwargs.get("message", "") for call in trigger.log.call_args_list)


@pytest.mark.parametrize(
    "stream,expected_event_count,expected_message_fragments",
    [
        (
            (
                b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"requestId": 1, "start": "1743505200"}}\n'
                b"not-a-json-line\n"
                b"[]\n"
                b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"requestId": 2, "start": "1743505201"}}\n'
                b'{"total": 2, "offset": "OFFSET_TOKEN"}\n'
            ),
            2,
            [
                "Skipped malformed JSON line in Akamai stream",
                "raw_line=not-a-json-line",
                "Skipped non-object JSON line in Akamai stream",
                "raw_item=[]",
            ],
        ),
        (
            (
                b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"requestId": 1, "start": "invalid"}}\n'
                b'{"total": 1, "offset": "OFFSET_TOKEN"}\n'
            ),
            1,
            ["Skipped checkpoint update because event timestamps are missing or invalid"],
        ),
        (
            (
                b'{"total": 1}\n'
                b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"requestId": 1, "start": "1743505200"}}\n'
                b'{"total": 1, "offset": "OFFSET_TOKEN"}\n'
            ),
            1,
            ["Skipped pagination context without offset"],
        ),
    ],
)
def test_fetch_events_logs_expected_warnings(
    trigger, response_2, stream, expected_event_count, expected_message_fragments
):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=stream,
        )
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
            status_code=200,
            content=response_2,
        )

        chunks = list(trigger.fetch_events())

    assert sum(len(chunk) for chunk in chunks) == expected_event_count
    for expected_fragment in expected_message_fragments:
        assert any(expected_fragment in call.kwargs.get("message", "") for call in trigger.log.call_args_list)


@pytest.mark.parametrize(
    "event,expected_request_id",
    [
        ({"type": "akamai_siem", "attackData": {}}, None),
        ({"httpMessage": {"requestId": "req-123"}}, "req-123"),
    ],
)
def test_get_event_request_id(event, expected_request_id):
    event_request_id = AkamaiWAFLogsConnector._get_event_request_id(event)

    assert event_request_id == expected_request_id


@pytest.mark.parametrize(
    "event,expected_start",
    [
        ({"httpMessage": "not-a-dict"}, None),
        ({"httpMessage": {"start": None}}, None),
        ({"httpMessage": {"start": "1743505200"}}, 1743505200),
        ({"httpMessage": {"start": "invalid"}}, None),
    ],
)
def test_get_event_start_timestamp(event, expected_start):
    event_start = AkamaiWAFLogsConnector._get_event_start_timestamp(event)

    assert event_start == expected_start


@pytest.mark.parametrize(
    "event,expect_none",
    [
        ({"httpMessage": {"start": "1743505200"}, "eventIndex": 1}, False),
        ({"httpMessage": {"start": "1743505200"}, "notSerializable": {1, 2}}, True),
    ],
)
def test_build_fallback_event_dedup_key(event, expect_none):
    dedup_key = AkamaiWAFLogsConnector._build_fallback_event_dedup_key(event)

    if expect_none:
        assert dedup_key is None
    else:
        assert dedup_key is not None
        assert dedup_key.startswith("fallback:")


def test_serialize_raw_log_value_truncates_oversized_payload(trigger):
    trigger.raw_log_max_length = 10

    serialized = trigger._serialize_raw_log_value({"payload": "x" * 100})

    assert serialized.startswith('{"payload"')
    assert "[truncated_raw_log chars=" in serialized
    assert "max_chars=10" in serialized


def test_fetch_events_logs_exception_when_process_event_fails(trigger, response_2):
    stream = (
        b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"requestId": 99, "start": "1743505200"}}\n'
        b'{"total": 1, "offset": "OFFSET_TOKEN"}\n'
    )

    with (
        patch.object(trigger, "process_event", side_effect=RuntimeError("boom")),
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=stream,
        )
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
            status_code=200,
            content=response_2,
        )

        chunks = list(trigger.fetch_events())

    assert chunks == []
    trigger.log_exception.assert_called_once()
    assert "Failed to process Akamai event" in trigger.log_exception.call_args.kwargs["message"]
    assert "raw_event={" in trigger.log_exception.call_args.kwargs["message"]


def test_fetch_events_deduplicates_identical_process_event_exceptions(trigger, response_2):
    repeated_failing_stream = (
        b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"requestId": 99, "start": "1743505200"}}\n'
        b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"requestId": 99, "start": "1743505200"}}\n'
        b'{"total": 2, "offset": "OFFSET_TOKEN"}\n'
    )

    with (
        patch.object(trigger, "process_event", side_effect=RuntimeError("boom")),
        requests_mock.Mocker() as mock_requests,
    ):
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=repeated_failing_stream,
        )
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
            status_code=200,
            content=response_2,
        )

        chunks = list(trigger.fetch_events())

    assert chunks == []
    trigger.log_exception.assert_called_once()


def test_fetch_events_skips_pagination_context_without_offset(trigger, response_2):
    stream = (
        b'{"total": 1}\n'
        b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"requestId": 1, "start": "1743505200"}}\n'
        b'{"total": 1, "offset": "OFFSET_TOKEN"}\n'
    )

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            status_code=200,
            content=stream,
        )
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
            status_code=200,
            content=response_2,
        )

        chunks = list(trigger.fetch_events())

    assert sum(len(chunk) for chunk in chunks) == 1
    assert any(
        "Skipped pagination context without offset" in call.kwargs.get("message", "")
        for call in trigger.log.call_args_list
    )


def test_filter_processed_events_logs_missing_request_id_for_each_event(trigger):
    events = [{"httpMessage": {"start": "1743505200"}, "eventIndex": i} for i in range(101)]

    filtered_events = list(trigger.filter_processed_events(events))

    assert len(filtered_events) == 101
    missing_id_logs = [
        call.kwargs.get("message", "")
        for call in trigger.log.call_args_list
        if "Forwarded event with fallback deduplication because requestId is missing" in call.kwargs.get("message", "")
    ]
    assert len(missing_id_logs) == 101
    assert all("occurrence=" not in message for message in missing_id_logs)


def test_filter_processed_events_forwards_when_fallback_dedup_key_generation_fails(trigger):
    event = {
        "httpMessage": {"start": "1743505200"},
        "notSerializable": {1, 2},
    }

    filtered_events = list(trigger.filter_processed_events([event]))

    assert filtered_events == [event]
    assert any(
        "fallback dedup key generation failed" in call.kwargs.get("message", "") for call in trigger.log.call_args_list
    )
    assert any("raw_event=" in call.kwargs.get("message", "") for call in trigger.log.call_args_list)


def test_next_batch_deduplicates_missing_request_id_when_timestamp_is_invalid(trigger, response_2):
    repeated_stream = (
        b'{"type": "akamai_siem", "attackData": {}, "httpMessage": {"start": "invalid"}}\n'
        b'{"total": 1, "offset": "OFFSET_TOKEN"}\n'
    )

    with patch("akamai_modules.connector_akamai_waf.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?from=1743505199&limit=60000",
            [{"status_code": 200, "content": repeated_stream}, {"status_code": 200, "content": repeated_stream}],
        )
        mock_requests.get(
            "https://example.com/siem/v1/configs/1?offset=OFFSET_TOKEN&limit=60000",
            [{"status_code": 200, "content": response_2}, {"status_code": 200, "content": response_2}],
        )

        mock_time.time.side_effect = [1666711174.0, 1666711235.0, 1666711296.0, 1666711357.0]
        trigger.next_batch()
        trigger.next_batch()

    assert trigger.push_events_to_intakes.call_count == 1
