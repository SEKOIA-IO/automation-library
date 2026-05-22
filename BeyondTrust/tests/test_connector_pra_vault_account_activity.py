from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from beyondtrust_modules import BeyondTrustModule
from beyondtrust_modules.connector_pra_vault_account_activity import BeyondTrustPRAVaultAccountActivityConnector


@pytest.fixture
def trigger(data_storage):
    module = BeyondTrustModule()
    module.configuration = {
        "base_url": "https://tenant.beyondtrustcloud.com",
        "client_id": "client_1",
        "client_secret": "SECRET",
    }
    trigger = BeyondTrustPRAVaultAccountActivityConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "intake_key": "intake_key",
    }
    yield trigger


def test_fetch_events(trigger, vault_activity_list):
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
            [{"content": vault_activity_list}],
        )

        trigger.from_date = 1773671925
        events = trigger.fetch_events()

        assert list(events) == [
            [
                {
                    "timestamp": "1773671926",
                    "event_type": "Account Created",
                    "account_id": "1",
                    "performed_by": {"id": "2", "type": "User", "name": "John Doe"},
                    "data": None,
                },
                {
                    "timestamp": "1773672020",
                    "event_type": "Password Changed",
                    "account_id": "1",
                    "performed_by": {"id": "2", "type": "User", "name": "John Doe"},
                    "data": "Manually Edited",
                },
                {
                    "timestamp": "1773672107",
                    "event_type": "Account Deleted",
                    "account_id": "1",
                    "performed_by": {"id": "2", "type": "User", "name": "John Doe"},
                    "data": None,
                },
            ]
        ]

        assert trigger.from_date == 1773672107


def test_next_batch_sleep_until_next_round(trigger, vault_activity_list):
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
            [{"content": vault_activity_list}],
        )

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_fetch_events_face_error(trigger):
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
