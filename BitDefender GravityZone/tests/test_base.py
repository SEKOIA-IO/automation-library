import json

import pytest
from requests import HTTPError, Response

from bitdefender.actions.scan_endpoint_action import ScanEndpointAction


def build_response(status_code: int, body: dict, reason: str = "OK") -> Response:
    response = Response()
    response.status_code = status_code
    response.reason = reason
    response._content = json.dumps(body).encode("utf-8")
    response.url = "https://gravityzone.example/api"
    return response


def test_base_action_helpers_and_error_paths(symphony_storage, monkeypatch):
    action = ScanEndpointAction(data_path=symphony_storage)
    action.module.configuration = {
        "api_key": "token",
        "url": "gravityzone.example/",
    }
    monkeypatch.setattr(action, "log", lambda *args, **kwargs: None)

    assert action.api_key == "token"
    assert action.get_api_url("api/v1.0/jsonrpc/incidents") == "https://gravityzone.example/api/v1.0/jsonrpc/incidents"

    with pytest.raises(ValueError, match="Endpoint API and body must be defined"):
        action.execute_request({"api": "", "body": {}})

    failing_response = build_response(500, {}, "Internal Server Error")
    with pytest.raises(HTTPError):
        action._handle_response_error(failing_response)

    api_error_response = build_response(200, {"error": {"message": "bad request", "data": {"field": "type"}}})
    with pytest.raises(ValueError, match="bad request - {'field': 'type'}"):
        action._handle_response_error(api_error_response)
