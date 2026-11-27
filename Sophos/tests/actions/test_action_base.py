from typing import Any
from unittest.mock import Mock

import pytest
import requests

from sophos_module.actions.action_base import SophosEDRAction
from tests.actions.conftest import API_HOST, DATA_REGION


class DummyAction(SophosEDRAction):
    def run(self, arguments: dict[str, Any]) -> Any:
        return None


@pytest.fixture
def action(module):
    return DummyAction(module)


@pytest.mark.parametrize("method", ["get", "GET", "post", "Post", "patch"])
@pytest.mark.parametrize("use_region_url, base_url", [(False, API_HOST), (True, DATA_REGION)])
def test_call_endpoint(action, mock_api, method, use_region_url, base_url):
    mock_api.register_uri(method.upper(), f"{base_url}/endpoint/v1/settings", json={"ok": True})

    result = action.call_endpoint(method, "endpoint/v1/settings", data={"a": 1}, use_region_url=use_region_url)

    assert result == {"ok": True}
    assert mock_api.last_request.method == method.upper()
    assert mock_api.last_request.json() == {"a": 1}


def test_region_base_url(action, mock_api):
    assert action.region_base_url == DATA_REGION


@pytest.mark.parametrize("status_code", [400, 404, 500])
def test_call_endpoint_error(action, mock_api, status_code):
    action.log = Mock()
    mock_api.post(
        f"{API_HOST}/endpoint/v1/settings",
        status_code=status_code,
        json={"error": "badRequest", "message": "Invalid request", "correlationId": "c"},
    )

    with pytest.raises(requests.HTTPError) as error:
        action.call_endpoint("post", "endpoint/v1/settings")
    assert error.value.response.status_code == status_code

    # one readable line in the action logs, with the ids for the Sophos support
    action.log.assert_called_once_with(
        message=f"The Sophos API call failed: status {status_code} - badRequest: Invalid request"
        f"{'. Error on the Sophos side, try again later' if status_code >= 500 else ''}"
        " (correlationId=c)",
        level="error",
    )


@pytest.mark.parametrize("method", ["delete", "put"])
def test_call_endpoint_unsupported_method(action, method):
    with pytest.raises(AssertionError):
        action.call_endpoint(method, "endpoint/v1/settings")
