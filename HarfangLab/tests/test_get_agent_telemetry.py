import requests_mock
from harfanglab.get_agent_telemetry import GetAgentTelemetry
import pytest


def test_integration_get_agent_telemetry():
    instance_url = "https://test.hurukau.io"
    api_token = "sss"

    module_configuration = {
        "api_token": api_token,
        "url": instance_url,
    }
    action = GetAgentTelemetry()
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mocked_response = {
            "count": 158,
            "next": None,
            "previous": None,
            "results": [
                {"host": "host1"},
                {"host": "host2"},
            ],
        }

        mock.get(
            f"{instance_url}/api/data/telemetry/Processes/",
            json=mocked_response,
            headers={"Authorization": f"Token {api_token}"},
        )

        arguments = {
            "agent_id": "7e19e65f-7c91-4cd6-b365-b0e603576f0d",
            "alert_created": "2025-04-29T17:54:49.326Z",
            "event_types": ["processes"],
        }
        response = action.run(arguments)
        assert response["data"] is not None
        assert len(response["data"]) == 2


def test_integration_get_agent_telemetry_next():
    instance_url = "https://test.hurukau.io"
    api_token = "sss"

    module_configuration = {
        "api_token": api_token,
        "url": instance_url,
    }
    action = GetAgentTelemetry()
    action.module.configuration = module_configuration

    with requests_mock.Mocker() as mock:
        mocked_response = {
            "count": 3,
            "next": "next_url",
            "previous": "previous_url",
            "results": [
                {"host": "host1"},
                {"host": "host2"},
            ],
        }

        mock.get(
            f"{instance_url}/api/data/telemetry/Processes/",
            json=mocked_response,
            headers={"Authorization": f"Token {api_token}"},
        )

        mocked_response_next = {
            "count": 3,
            "next": None,
            "previous": None,
            "results": [{"host": "host3"}],
        }

        mock.get(
            f"{instance_url}/api/data/telemetry/Processes/?offset=2",
            json=mocked_response_next,
            headers={"Authorization": f"Token {api_token}"},
        )

        arguments = {
            "agent_id": "7e19e65f-7c91-4cd6-b365-b0e603576f0d",
            "alert_created": "2025-04-29T17:54:49.326Z",
            "event_types": ["processes"],
        }
        response = action.run(arguments)
        assert response["data"] is not None
        assert len(response["data"]) == 3


def test_integration_get_agent_telemetry_wrong_event_type():
    instance_url = "https://test.hurukau.io"
    api_token = "sss"

    module_configuration = {
        "api_token": api_token,
        "url": instance_url,
    }
    action = GetAgentTelemetry()
    action.module.configuration = module_configuration

    arguments = {
        "agent_id": "7e19e65f-7c91-4cd6-b365-b0e603576f0d",
        "alert_created": "2025-04-29T17:54:49.326Z",
        "event_types": ["test"],
    }
    with pytest.raises(ValueError):
        action.run(arguments)
