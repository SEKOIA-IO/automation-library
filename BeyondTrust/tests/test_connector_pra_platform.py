from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from beyondtrust_modules import BeyondTrustModule
from beyondtrust_modules.connector_pra_platform import BeyondTrustPRAPlatformConfiguration
from beyondtrust_modules.connector_pra_platform import BeyondTrustPRAPlatformConnector
from beyondtrust_modules.models import BeyondTrustModuleConfiguration

from .expectations import EXPECTED_SESSION_EVENTS


@pytest.fixture
def trigger(data_storage):
    module = BeyondTrustModule()
    module.configuration = BeyondTrustModuleConfiguration(
        base_url="https://tenant.beyondtrustcloud.com",
        client_id="client_1",
        client_secret="SECRET",
    )
    trigger = BeyondTrustPRAPlatformConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = BeyondTrustPRAPlatformConfiguration(
        intake_key="intake_key",
        frequency=300,
    )
    yield trigger


def test_fetch_events(trigger, sessions_list_xml_with_one, session_xml):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri(
            "POST",
            f"https://tenant.beyondtrustcloud.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            [{"content": sessions_list_xml_with_one}, {"content": session_xml}],
        )

        trigger.from_date = 1732810704
        events = trigger.fetch_events()

        assert list(events) == [EXPECTED_SESSION_EVENTS]

        assert trigger.from_date == 1733240467
        assert trigger.sessions_cache["e9e99aeb9ad54fb381634498502c5a1b"] == 1


def test_next_batch_sleep_until_next_round(trigger, sessions_list_xml_with_one, session_xml):
    with patch("beyondtrust_modules.connector_base.time") as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri(
            "POST",
            f"https://tenant.beyondtrustcloud.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            [{"content": sessions_list_xml_with_one}, {"content": session_xml}],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_fetch_events_face_error(trigger, sessions_list_xml_with_one, session_xml):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri(
            "POST",
            f"https://tenant.beyondtrustcloud.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            status_code=500,
            json={"error": "Internal Server Error"},
        )

        trigger.from_date = 1732810704
        events = trigger.fetch_events()

        assert list(events) == []


def test_fetch_events_xml_error_with_attributes(trigger, error_response_xml):
    """Test that error responses containing <error> tags with XML attributes are properly detected and logged."""
    with requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri(
            "POST",
            f"https://tenant.beyondtrustcloud.com/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            status_code=200,
            content=error_response_xml,
        )

        trigger.from_date = 1732810704
        events = trigger.fetch_events()

        assert list(events) == []
        # Verify that the error was logged with the expected format
        expected_error_msg = f"An error occurred. response: {error_response_xml.decode('utf-8')}"
        trigger.log.assert_any_call(expected_error_msg, level="error")


def test_load_cache_and_skip_cached_session(trigger):
    with trigger.cursor._context as cache:
        cache["sessions_cache"] = ["cached-session-id"]

    loaded = trigger.load_sessions_cache()
    assert "cached-session-id" in loaded
    trigger.sessions_cache = loaded

    session_listing = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<session_summary_list xmlns=\"http://www.beyondtrust.com/sra/namespaces/API/reporting\">
<session_summary lsid=\"cached-session-id\" has_recording=\"0\"/>
</session_summary_list>"""

    with requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/oauth2/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            [{"content": session_listing}],
        )

        assert list(trigger.fetch_events()) == []


def test_return_on_get_session_error(trigger):
    session_listing = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<session_summary_list xmlns=\"http://www.beyondtrust.com/sra/namespaces/API/reporting\">
<session_summary lsid=\"new-session-id\" has_recording=\"0\"/>
</session_summary_list>"""

    with requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/oauth2/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            [{"content": session_listing}, {"status_code": 500, "json": {"message": "boom"}}],
        )

        assert list(trigger.fetch_events()) == []
