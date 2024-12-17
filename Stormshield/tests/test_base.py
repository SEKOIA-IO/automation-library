import pytest
from unittest.mock import MagicMock

from stormshield_module.endpoint_actions import EndpointAgentIsolationAction


def test_base_get_headers(symphony_storage):
    module_configuration = {
        "api_token": "token",
        "url": "https://stormshield-api-example.eu/",
    }
    action = EndpointAgentIsolationAction(data_path=symphony_storage)
    action.module.configuration = module_configuration
    header = action.get_headers()
    assert header == {"Authorization": "Bearer token"}


def test_base_get_url(symphony_storage):
    module_configuration = {
        "api_token": "token",
        "url": "https://stormshield-api-example.eu/",
    }
    action = EndpointAgentIsolationAction(data_path=symphony_storage)
    action.module.configuration = module_configuration
    url = action.get_url({"id": "foo"})
    assert url == "https://stormshield-api-example.eu/rest/api/v1/agents/foo/tasks/network-isolation"


def test_treat_failed_response_authentication_failed_401(symphony_storage):
    action = EndpointAgentIsolationAction(data_path=symphony_storage)
    response = MagicMock()
    response.status_code = 401

    with pytest.raises(Exception) as excinfo:
        action.treat_failed_response(response)

    assert str(excinfo.value) == f"Error : Authentication failed: Invalid API key provided."


def test_treat_failed_response_authentication_failed_500(symphony_storage):
    action = EndpointAgentIsolationAction(data_path=symphony_storage)
    response = MagicMock()
    response.status_code = 500

    with pytest.raises(Exception) as excinfo:
        action.treat_failed_response(response)

    assert str(excinfo.value) == f"Error : Internal server error: Rate limit exceeded."
