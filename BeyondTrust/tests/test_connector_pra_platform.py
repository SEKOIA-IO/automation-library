from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from beyondtrust_modules import BeyondTrustModule
from beyondtrust_modules.connector_pra_platform import BeyondTrustPRAPlatformConnector


@pytest.fixture
def trigger(data_storage):
    module = BeyondTrustModule()
    module.configuration = {
        "base_url": "https://tenant.beyondtrustcloud.com",
        "client_id": "client_1",
        "client_secret": "SECRET",
    }
    trigger = BeyondTrustPRAPlatformConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "intake_key": "intake_key",
    }
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

        # mock_requests.get("https://tenant_id.okta.com/api/v1/logs", status_code=200, json=messages)
        trigger.from_date = 1732810704
        events = trigger.fetch_events()

        assert list(events) == [
            [
                {
                    "timestamp": "1733239565",
                    "event_type": "Session Start",
                    "session_id": "e9e99aeb9ad54fb381634498502c5a1b",
                    "jump_group": {"name": "Sekoia.io integration", "type": "shared"},
                },
                {
                    "timestamp": "1733239565",
                    "event_type": "Conference Owner Changed",
                    "data": {"owner": "Pre-start Conference"},
                    "destination": {"type": "system", "name": "Pre-start Conference"},
                    "session_id": "e9e99aeb9ad54fb381634498502c5a1b",
                    "jump_group": {"name": "Sekoia.io integration", "type": "shared"},
                },
            ]
        ]

        assert trigger.from_date == 1733240467
        assert trigger.sessions_cache["e9e99aeb9ad54fb381634498502c5a1b"] == 1


def test_next_batch_sleep_until_next_round(trigger, sessions_list_xml_with_one, session_xml):
    with patch(
        "beyondtrust_modules.connector_pra_platform.time"
    ) as mock_time, requests_mock.Mocker() as mock_requests:
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
