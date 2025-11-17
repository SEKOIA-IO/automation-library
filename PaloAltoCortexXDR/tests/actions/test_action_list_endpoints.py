from unittest.mock import Mock

import pytest
import requests_mock

from cortex_module.actions.action_list_endpoints import ListEndpointsAction


@pytest.fixture
def action(module, symphony_storage):
    action = ListEndpointsAction(module=module, data_path=symphony_storage)

    action.log_exception = Mock()
    action.log = Mock()

    return action


def test_run_action(action):
    fqdn = action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/endpoints/get_endpoints"

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={
                "reply": [
                    {
                        "agent_id": "123",
                        "host_name": "test-endpoint",
                        "agent_type": "Workstation",
                        "agent_status": "Disconnected",
                    }
                ]
            },
            additional_matcher=lambda request: request.json() == {},
        )

        result = action.run({})
        assert result == {
            "reply": [
                {
                    "agent_id": "123",
                    "host_name": "test-endpoint",
                    "agent_type": "Workstation",
                    "agent_status": "Disconnected",
                }
            ]
        }


def test_run_action_empty_response(action):
    fqdn = action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/endpoints/get_endpoints"

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={"reply": []},
            additional_matcher=lambda request: request.json() == {},
        )

        result = action.run({})
        assert result == {"reply": []}


def test_run_action_error_response(action):
    fqdn = action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/endpoints/get_endpoints"

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={"reply": {"err_code": 500, "err_msg": "Internal server error"}},
            additional_matcher=lambda request: request.json() == {},
        )

        with pytest.raises(ValueError, match="Error in response: 500 - Internal server error"):
            action.run({})
