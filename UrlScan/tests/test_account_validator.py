from unittest.mock import Mock

import httpx
import pytest
import respx

from urlscan_modules import UrlScanModule
from urlscan_modules.account_validator import UrlScanAccountValidator


@pytest.fixture
def validator(module: UrlScanModule, tmp_path) -> UrlScanAccountValidator:
    validator = UrlScanAccountValidator(module=module, data_path=tmp_path)
    validator.error = Mock()
    validator.log = Mock()
    return validator


def test_valid_key(validator: UrlScanAccountValidator, api: respx.MockRouter):
    route = api.get("/api/v1/quotas").respond(200, json={"scope": "team"})

    assert validator.validate() is True

    validator.error.assert_not_called()
    assert route.call_count == 1
    assert route.calls.last.request.headers["API-Key"] == "test-api-key"


def test_invalid_key(validator: UrlScanAccountValidator, api: respx.MockRouter):
    api.get("/api/v1/quotas").respond(401, json={"message": "API key supplied but not found in database!"})

    assert validator.validate() is False

    validator.error.assert_called_once_with("Invalid urlscan.io API key")
    assert validator.log.call_args.kwargs["level"] == "error"


def test_unreachable(validator: UrlScanAccountValidator, api: respx.MockRouter):
    api.get("/api/v1/quotas").mock(side_effect=httpx.ConnectError("boom"))

    assert validator.validate() is False

    validator.error.assert_called_once_with("urlscan.io could not be reached: ConnectError")
