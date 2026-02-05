import json
import pytest
from unittest import mock
from unittest.mock import ANY, MagicMock, patch

from usta_modules.models import UstaATPConnectorConfiguration, UstaModuleConfig
from usta_modules.usta_atp_connector import UstaAPIError, UstaAtpConnector


class StopTest(Exception):
    pass


def test_happy_path(atp_connector: UstaAtpConnector):
    compromised_credentials_events = [
        {
            "company": {"id": 0, "name": "string"},
            "content": {
                "is_corporate": True,
                "password": "string",
                "password_complexity": {
                    "contains": {
                        "lowercase": 0,
                        "numbers": 0,
                        "other": 0,
                        "punctuation": 0,
                        "separators": 0,
                        "symbols": 0,
                        "uppercase": 0,
                    },
                    "length": 0,
                    "score": "very_weak",
                },
                "source": "malware",
                "url": "http://example.com",
                "username": "string",
                "victim_detail": {
                    "computer_name": "string",
                    "country": "string",
                    "cpu": "string",
                    "gpu": "string",
                    "infection_date": "string",
                    "ip": "string",
                    "language": "string",
                    "malware": "string",
                    "memory": "string",
                    "phone_number": "string",
                    "username": "string",
                    "victim_os": "string",
                    "victim_uid": "9eee4f4d-714d-402f-b9c1-17d4442e0901",
                },
            },
            "content_type": "string",
            "created": "2019-08-24T14:15:22Z",
            "id": 0,
            "status": "in_progress",
            "status_timestamp": "2019-08-24T14:15:22Z",
        }
    ]

    with (
        patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client,
        patch("time.sleep", side_effect=StopTest),
    ):
        mock_instance = mock_usta_client.return_value
        mock_instance.iter_compromised_credentials.return_value = compromised_credentials_events
        atp_connector.push_events_to_intakes(events=[json.dumps(event) for event in compromised_credentials_events])

        # When
        try:
            atp_connector.run()
        except StopTest:
            pass

        # Then
        atp_connector.push_events_to_intakes.assert_called_once_with(
            events=[json.dumps(event) for event in compromised_credentials_events],
        )


def test_forward_empty_list_of_events(atp_connector: UstaAtpConnector):
    # Given
    with (
        patch("usta_modules.usta_atp_connector.UstaClient") as mock_usta_client,
        patch("time.sleep", side_effect=StopTest),
    ):
        mock_instance = mock_usta_client.return_value
        mock_instance.iter_compromised_credentials.return_value = []

        # When
        try:
            atp_connector.run()
        except StopTest:
            pass

        # Then
        atp_connector.push_events_to_intakes.assert_not_called()


def test_missing_api_key(atp_connector: UstaAtpConnector):
    # Given
    atp_connector.module.configuration.api_key = ""

    # When
    with pytest.raises(ValueError) as excinfo:
        atp_connector.run()

    # Then
    assert "Authorization token must be provided." in str(excinfo.value)
    atp_connector.push_events_to_intakes.assert_not_called()
