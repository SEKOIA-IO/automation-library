import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock

import pytest
import requests
import requests_mock

from hornetsecurity_modules import HornetsecurityModule
from hornetsecurity_modules.connector_smp_events import Direction, SMPEventsConnector, SMPEventsConnectorConfiguration
from hornetsecurity_modules.errors import FailedEmailHeaderFetchError, InvalidObjectIdError, UnknownObjectIdError
from hornetsecurity_modules.models import HornetsecurityModuleConfiguration


@pytest.fixture
def smp_events_connector(module, data_storage):
    """
    Fixture to create an instance of SMPEventsConnector for testing.
    """
    connector = SMPEventsConnector(module=module, data_path=data_storage)
    connector.configuration = SMPEventsConnectorConfiguration(
        scope="test@example.com",
        direction="Both",
        include_header=False,
        frequency=300,
        chunk_size=2000,
        timedelta=0,
        ratelimit_per_second=20,
        intake_key="fake_intake_key",
    )
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    connector.time_stepper.ranges = Mock(
        side_effect=[
            [
                (
                    datetime.now(timezone.utc) - timedelta(minutes=5),
                    datetime.now(timezone.utc),
                )
            ]
        ]
    )
    return connector


@pytest.fixture
def event1():
    return {
        "direction": 1,
        "date": "2025-06-12T14:26:00Z",
        "msg_id": "11111111111111111111111111111111111111111111111111111111111111111",
        "source_hostname": "malicious.example.com",
        "destination_hostname": "smtp.example.net",
        "gateway": "mx-gate1-ex",
        "source_ip": "1.2.3.4",
        "destination_ip": "5.6.7.8",
        "message_id": "1111111111111111111111111111111111111111",
        "smtp_dialog": [
            "2025-06-12T14:26:00Z;SMTP;smtp.example.net[5.6.7.8];250 2.0.0 Ok: queued as F127D17407D7;END_SEND;CIPHER=NONE;IDENTITY=NONE;TLS_VER=NONE;TLS_CSUITE=NONE;TLS_WARN=NONE"
        ],
        "smtp_status": "2025-06-12T14:26:00Z;SMTP;smtp.example.net[5.6.7.8];250 2.0.0 Ok: queued as F127D17407D7;END_SEND;CIPHER=NONE;IDENTITY=NONE;TLS_VER=NONE;TLS_CSUITE=NONE;TLS_WARN=NONE",
        "owner": "test@example.net",
        "owner_domain": "example.net",
        "comm_partner": "malicious@example.com",
        "smtp_status_code": 250,
        "last_remediation_actions": "",
        "last_remediation_type": "",
        "last_remediation_folder": "",
        "last_remediation_effectiveness": "",
        "last_report_type": "",
        "has_url_rewritten": False,
        "history": "",
        "is_archived": False,
        "fix_ids": "",
        "es_mail_id": "rk5Jm1-BQEmieVi61uwiX",
        "crypt_type_in": {"id": 7, "text": "TLS"},
        "crypt_type_out": {"id": 1, "text": "NONE"},
        "classification": {"id": 2, "text": "clean"},
        "status": {"id": 1, "text": "Delivered"},
        "size": {"value": 0, "unit": "KB"},
        "private": False,
        "reason": "good sender reputation",
        "subject": "ELT Log Event [ID:07b1578b73e9e928] [20250612-1625] [To:test@example.com]",
        "attachments": [],
        "last_remediation": {
            "remediation_type": None,
            "remediation_actions": None,
            "remediation_folder": None,
            "remediation_tag": None,
            "remediation_effectiveness": False,
            "report_type": None,
            "has_url_rewritten": False,
        },
    }


@pytest.fixture
def event2():
    return {
        "direction": 1,
        "date": "2025-06-12T13:50:36Z",
        "msg_id": "22222222222222222222222222222222222222222222222222222222222222222",
        "source_hostname": "malicious.example.com",
        "destination_hostname": "smtp.example.net",
        "gateway": "mx-gate109-hz1",
        "source_ip": "1.2.3.4",
        "destination_ip": "5.6.7.8",
        "message_id": "22222222222222222222222222222222",
        "smtp_dialog": [
            "2025-06-12T13:50:36Z;SMTP;smtp.example.net[5.6.7.8];250 2.0.0 Ok: queued as A49261740540;END_SEND;CIPHER=NONE;IDENTITY=NONE;TLS_VER=NONE;TLS_CSUITE=NONE;TLS_WARN=NONE"
        ],
        "smtp_status": "2025-06-12T13:50:36Z;SMTP;smtp.example.net[5.6.7.8];250 2.0.0 Ok: queued as A49261740540;END_SEND;CIPHER=NONE;IDENTITY=NONE;TLS_VER=NONE;TLS_CSUITE=NONE;TLS_WARN=NONE",
        "owner": "test@example.net",
        "owner_domain": "example.net",
        "comm_partner": "malicious@example.com",
        "smtp_status_code": 250,
        "last_remediation_actions": "",
        "last_remediation_type": "",
        "last_remediation_folder": "",
        "last_remediation_effectiveness": "",
        "last_report_type": "",
        "has_url_rewritten": False,
        "history": "",
        "is_archived": False,
        "fix_ids": "",
        "es_mail_id": "uRuIMYkiA0DBZRSzT9ls5",
        "crypt_type_in": {"id": 7, "text": "TLS"},
        "crypt_type_out": {"id": 1, "text": "NONE"},
        "classification": {"id": 2, "text": "clean"},
        "status": {"id": 1, "text": "Delivered"},
        "size": {"value": 0, "unit": "KB"},
        "private": False,
        "reason": "good sender reputation",
        "subject": "ELT Log Event [ID:0f50cc1aa96581f2] [20250612-1550] [To:test@example.net]",
        "attachments": [],
        "last_remediation": {
            "remediation_type": None,
            "remediation_actions": None,
            "remediation_folder": None,
            "remediation_tag": None,
            "remediation_effectiveness": False,
            "report_type": None,
            "has_url_rewritten": False,
        },
    }


@pytest.mark.parametrize(
    "direction, expected_result",
    [
        (Direction.BOTH, None),
        (Direction.INCOMING, 1),
        (Direction.OUTGOING, 2),
    ],
)
def test_direction_to_id(direction, expected_result):
    """
    Test the configuration of SMPEventsConnector.
    """
    assert direction.to_id() == expected_result


def test_connector_handle_response_ok(smp_events_connector):
    """
    Test the handle_response method of SMPEventsConnector.
    """
    mock_response = Mock(spec=requests.Response)
    mock_response.ok = True
    mock_response.status_code = 200

    smp_events_connector.handle_response(mock_response)

    # Ensure no errors are logged when the response is OK
    smp_events_connector.log.assert_not_called()


def test_connector_handle_response_not_found(smp_events_connector):
    """
    Test the handle_response method of SMPEventsConnector.
    """
    mock_response = Mock(spec=requests.Response)
    mock_response.ok = False
    mock_response.status_code = 404
    mock_response.reason = "Not Found"
    mock_response.json.return_value = {
        "error_id": "404",
        "error_data": "Invalid location for /events",
        "error_message": "Resource not found",
    }

    smp_events_connector.handle_response(mock_response)

    # Ensure the error is logged correctly
    smp_events_connector.log.assert_called_once_with(
        level="error",
        message="Request failed with status code 404 - Not Found - error id: 404 - error message: Resource not found - error data: Invalid location for /events",
    )


def test_connector_handle_response_unauthorized(smp_events_connector):
    """
    Test the handle_response method of SMPEventsConnector.
    """
    mock_response = Mock(spec=requests.Response)
    mock_response.ok = False
    mock_response.status_code = 401
    mock_response.reason = "Unauthorized"
    mock_response.json.return_value = {
        "error_id": "401",
        "error_data": "Invalid authentication token",
        "error_message": "Unauthorized access",
    }

    smp_events_connector.handle_response(mock_response)

    # Ensure the error is logged correctly
    smp_events_connector.log.assert_called_once_with(
        level="critical",
        message="Request failed with status code 401 - Unauthorized - error id: 401 - error message: Unauthorized access - error data: Invalid authentication token",
    )


@pytest.mark.parametrize(
    "scope, response_status_code, response_json, expected_result",
    [
        ("12345", 200, {"object_id": 12345}, 12345),
        ("example.com", 200, {"object_id": 67890}, 67890),
        (
            "invalid_scope",
            404,
            {"error_id": "404", "error_message": "Object not found"},
            UnknownObjectIdError,
        ),
        ("example.com", 200, {"object_id": "string"}, InvalidObjectIdError),
        ("example.com", 200, {}, UnknownObjectIdError),
    ],
)
def test_get_object_id_from_scope(smp_events_connector, scope, response_status_code, response_json, expected_result):
    """
    Test the get_object_id_from_scope method of SMPEventsConnector.
    """
    with requests_mock.Mocker() as m:
        m.get(
            f"https://cp.hornetsecurity.com/api/v0/object/?name={scope}",
            json=response_json,
            status_code=response_status_code,
        )
        if isinstance(expected_result, type) and issubclass(expected_result, Exception):
            with pytest.raises(expected_result):
                smp_events_connector.get_object_id_from_scope(scope)
        else:
            result = smp_events_connector.get_object_id_from_scope(scope)
            assert result == expected_result


@pytest.mark.parametrize(
    "object_id, es_mail_id, response_status_code, response_json, expected_result",
    [
        (
            12345,
            "abcde",
            200,
            {"raw_header": "Sample email header"},
            "Sample email header",
        ),
        (
            12345,
            "abcde",
            404,
            {"error_id": "404", "error_message": "Email not found"},
            FailedEmailHeaderFetchError,
        ),
    ],
)
def test_get_email_header(
    smp_events_connector,
    object_id,
    es_mail_id,
    response_status_code,
    response_json,
    expected_result,
):
    """
    Test the get_EmailHeader method of SMPEventsConnector.
    """
    with requests_mock.Mocker() as m:
        m.post(
            f"https://cp.hornetsecurity.com/api/v0/emails/header/?object_id={object_id}",
            json=response_json,
            status_code=response_status_code,
        )

        if isinstance(expected_result, type) and issubclass(expected_result, Exception):
            with pytest.raises(expected_result):
                smp_events_connector.get_email_header(object_id, es_mail_id)
        else:
            header = smp_events_connector.get_email_header(object_id, es_mail_id)
            assert header == expected_result


def test_enrich_event_with_email_header(smp_events_connector):
    """
    Test the enrich_event_with_email_header method of SMPEventsConnector.
    """
    event = {
        "es_mail_id": "abcde",
    }

    smp_events_connector.get_object_id_from_scope = Mock(return_value=12345)
    smp_events_connector.get_email_header = Mock(return_value="Sample email header")

    enriched_event = smp_events_connector.enrich_event_with_header(event, True)
    assert enriched_event.get("raw_header") == "Sample email header"


def test_no_enrich_event_with_email_header(smp_events_connector):
    """
    Test the enrich_event_with_email_header method of SMPEventsConnector.
    """
    event = {
        "es_mail_id": "abcde",
    }

    smp_events_connector.get_object_id_from_scope = Mock(return_value=12345)
    smp_events_connector.get_email_header = Mock(return_value="Sample email header")

    enriched_event = smp_events_connector.enrich_event_with_header(event, False)
    assert enriched_event.get("raw_header") is None


def test_enrich_event_with_email_header_failed(smp_events_connector):
    """
    Test the enrich_event_with_email_header method of SMPEventsConnector when fetching the header fails.
    """
    event = {
        "es_mail_id": "abcde",
    }

    smp_events_connector.get_object_id_from_scope = Mock(return_value=12345)
    smp_events_connector.get_email_header = Mock(side_effect=FailedEmailHeaderFetchError(12345, "abcde"))

    enriched_event = smp_events_connector.enrich_event_with_header(event, True)
    assert enriched_event.get("raw_header") is None
    smp_events_connector.log.assert_called_once()


def test_fetch_events_unauthorized(smp_events_connector):
    """
    Test the _fetch_events method of SMPEventsConnector when unauthorized.
    """
    with requests_mock.Mocker() as m:
        m.get(
            "https://cp.hornetsecurity.com/api/v0/object/",
            json={"object_id": 12345},
            status_code=200,
        )
        m.post(
            "https://cp.hornetsecurity.com/api/v0/emails/_search/",
            status_code=401,
            json={"error_id": "401", "error_message": "Unauthorized access"},
        )

        events_gen = smp_events_connector._fetch_events(
            datetime(2023, 10, 1, 11, 55, tzinfo=timezone.utc),
            datetime(2023, 10, 1, 12, 5, tzinfo=timezone.utc),
        )

        with pytest.raises(StopIteration):
            next(events_gen)

        assert smp_events_connector.log.called


def test_fetch_no_connect(smp_events_connector):
    """
    Test the _fetch_events method of SMPEventsConnector when no content is returned.
    """
    with requests_mock.Mocker() as m:
        m.get(
            "https://cp.hornetsecurity.com/api/v0/object/",
            json={"object_id": 12345},
            status_code=200,
        )
        m.post(
            "https://cp.hornetsecurity.com/api/v0/emails/_search/",
            status_code=200,
        )

        events_gen = smp_events_connector._fetch_events(
            datetime(2023, 10, 1, 11, 55, tzinfo=timezone.utc),
            datetime(2023, 10, 1, 12, 5, tzinfo=timezone.utc),
        )

        with pytest.raises(StopIteration):
            next(events_gen)

        smp_events_connector.log.assert_any_call(level="error", message="Failed to parse response content")


def test_fetch_no_events(smp_events_connector):
    """
    Test the _fetch_events method of SMPEventsConnector when no emails are found in the response.
    """
    with requests_mock.Mocker() as m:
        m.get(
            "https://cp.hornetsecurity.com/api/v0/object/",
            json={"object_id": 12345},
            status_code=200,
        )
        m.post(
            "https://cp.hornetsecurity.com/api/v0/emails/_search/",
            status_code=200,
            json={"emails": [], "num_found_items": 0},
        )

        events_gen = smp_events_connector._fetch_events(
            datetime(2023, 10, 1, 11, 55, tzinfo=timezone.utc),
            datetime(2023, 10, 1, 12, 5, tzinfo=timezone.utc),
        )

        with pytest.raises(StopIteration):
            next(events_gen)

        smp_events_connector.log.assert_any_call(level="info", message="No emails found in the response.")


def test_fetch_events(smp_events_connector, event1, event2):
    """
    Test the _fetch_events method of SMPEventsConnector.
    """
    with requests_mock.Mocker() as m:
        m.get(
            "https://cp.hornetsecurity.com/api/v0/object/",
            json={"object_id": 12345},
            status_code=200,
        )
        m.post(
            "https://cp.hornetsecurity.com/api/v0/emails/_search/",
            json={"emails": [event1, event2], "num_found_items": 2},
            status_code=200,
        )

        events_list = list(
            smp_events_connector._fetch_events(
                datetime(2023, 10, 1, 11, 55, tzinfo=timezone.utc),
                datetime(2023, 10, 1, 12, 5, tzinfo=timezone.utc),
            )
        )

        assert len(events_list) == 1

        events = events_list[0]
        assert len(events) == 2
        assert events[0]["msg_id"] == event1["msg_id"]
        assert events[1]["msg_id"] == event2["msg_id"]


def test_fetch_events_with_direction(module, data_storage, event1, event2):
    """
    Test the fetch_events method of SMPEventsConnector.
    """
    connector = SMPEventsConnector(module=module, data_path=data_storage)
    connector.configuration = SMPEventsConnectorConfiguration(
        scope="test@example.com",
        direction="Incoming",
        include_header=False,
        frequency=300,
        chunk_size=1,
        timedelta=0,
        ratelimit_per_second=20,
        intake_key="fake_intake_key",
    )
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    connector.time_stepper.ranges = Mock(
        side_effect=[
            [
                (
                    datetime.now(timezone.utc) - timedelta(minutes=5),
                    datetime.now(timezone.utc),
                )
            ]
        ]
    )
    with requests_mock.Mocker() as m:
        m.get(
            "https://cp.hornetsecurity.com/api/v0/object/",
            json={"object_id": 12345},
            status_code=200,
        )
        m.post(
            "https://cp.hornetsecurity.com/api/v0/emails/_search/",
            [
                {
                    "status_code": 200,
                    "json": {"emails": [event1], "num_found_items": 3},
                },
                {
                    "status_code": 200,
                    "json": {"emails": [event1], "num_found_items": 3},
                },  # Response with a already fetched event - must be discarded
                {
                    "status_code": 200,
                    "json": {"emails": [event2], "num_found_items": 3},
                },
                {
                    "status_code": 200,
                    "json": {"emails": [], "num_found_items": 3},
                },  # No more events - must be discarded
            ],
        )

        events_list = list(connector.fetch_events())

        # We also check the deduplication of events
        assert len(events_list) == 2

        assert events_list[0][0]["msg_id"] == event1["msg_id"]
        assert events_list[1][0]["msg_id"] == event2["msg_id"]


@pytest.mark.skipif(
    "{'HORNETSECURITY_BASE_URL', 'HORNETSECURITY_API_TOKEN', 'HORNETSECURITY_SCOPE'} \
    .issubset(os.environ.keys()) == False"
)
def test_next_batch_integration(data_storage):
    """
    Test the fetch_events method of SMPEventsConnector.
    """
    module = HornetsecurityModule()
    module.configuration = HornetsecurityModuleConfiguration(
        api_token=os.environ["HORNETSECURITY_API_TOKEN"],
        api_url=os.environ["HORNETSECURITY_BASE_URL"],
    )
    connector = SMPEventsConnector(module=module, data_path=data_storage)
    connector.configuration = SMPEventsConnectorConfiguration(
        scope=os.environ["HORNETSECURITY_SCOPE"],
        direction="Incoming",
        include_header=False,
        frequency=300,
        chunk_size=2000,
        timedelta=0,
        ratelimit_per_second=20,
        intake_key="fake_intake_key",
    )
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    connector.time_stepper.ranges = Mock(
        side_effect=[
            [
                (
                    datetime.now(timezone.utc) - timedelta(hours=1),
                    datetime.now(timezone.utc),
                )
            ]
        ]
    )

    connector.next_batch()
    assert connector.push_events_to_intakes.call_count > 0
    assert connector.log_exception.call_count == 0
