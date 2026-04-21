from unittest.mock import patch

import pytest

from stormshieldSNS.block_ip_action import BlockIPAddressAction
from stormshieldSNS.models.common_models import StormshieldSNSConfiguration, StormshieldSNSModule


class MockResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("No JSON body")
        return self._payload


def configured_action() -> BlockIPAddressAction:
    module = StormshieldSNSModule()
    action = BlockIPAddressAction(module)
    action.module.configuration = StormshieldSNSConfiguration(
        url="https://sns.example.local/",
        api_token="token",
    )
    return action


@patch("stormshieldSNS.client.sns_client.requests.request")
def test_block_ip_success(mock_request):
    action = configured_action()
    mock_request.return_value = MockResponse(
        201,
        {
            "success": True,
            "result": {
                "code": "ESUCCESS",
                "securitylevel": "NONE",
                "message": "The address/range has been added to the banned ip list.",
                "value": "Entry added.",
            },
        },
    )

    result = action.run({"ip_address": "1.2.3.4", "duration_s": 3600})

    assert result["status"] == "success"
    assert result["ip_address"] == "1.2.3.4"
    assert result["duration_s"] == 3600
    assert result["message"] == "The address/range has been added to the banned ip list."


@patch("stormshieldSNS.client.sns_client.requests.request")
def test_block_ip_invalid_ip(mock_request):
    action = configured_action()

    with pytest.raises(ValueError):
        action.run({"ip_address": "not_an_ip"})

    mock_request.assert_not_called()


@patch("stormshieldSNS.client.sns_client.requests.request")
def test_block_ip_api_error(mock_request):
    action = configured_action()
    mock_request.return_value = MockResponse(401, {"error": "unauthorized"})

    with pytest.raises(RuntimeError, match="Failed to block IP"):
        action.run({"ip_address": "8.8.8.8", "duration_s": 3600})


@patch("stormshieldSNS.client.sns_client.requests.request")
def test_block_ip_conflict(mock_request):
    action = configured_action()
    mock_request.return_value = MockResponse(
        409,
        {
            "result": {
                "code": "ECONFLICT",
                "message": "At least one address can't be added because it is in static configuration.",
            }
        },
    )

    with pytest.raises(RuntimeError, match="Failed to block IP"):
        action.run({"ip_address": "5.6.7.8", "duration_s": 3600})
