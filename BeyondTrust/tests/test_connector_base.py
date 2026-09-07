from typing import cast
from unittest.mock import MagicMock

import pytest
import requests

from beyondtrust_modules import BeyondTrustModule
from beyondtrust_modules.connector_base import BeyondTrustBaseConnector
from beyondtrust_modules.connector_pra_platform import BeyondTrustPRAPlatformConfiguration
from beyondtrust_modules.models import BeyondTrustModuleConfiguration


class _FakeResponse:
    def __init__(
        self,
        *,
        ok=True,
        status_code=200,
        reason="OK",
        text="",
        headers=None,
        json_data=None,
        json_exc=None,
    ):
        self.ok = ok
        self.status_code = status_code
        self.reason = reason
        self.text = text
        self.headers = headers or {}
        self._json_data = json_data or {}
        self._json_exc = json_exc

    def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._json_data


class _BaseConnectorForTests(BeyondTrustBaseConnector):
    def __init__(self, *args, batches=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._batches = batches if batches is not None else []

    def fetch_events(self):
        for batch in self._batches:
            yield batch


def _build_module() -> BeyondTrustModule:
    module = BeyondTrustModule()
    module.configuration = BeyondTrustModuleConfiguration(
        base_url="https://tenant.beyondtrustcloud.com",
        client_id="client_1",
        client_secret="SECRET",
    )
    return module


def test_handle_response_error_json_exception_and_critical_level(data_storage):
    connector = _BaseConnectorForTests(module=_build_module(), data_path=data_storage)
    connector.log = MagicMock()

    response_500 = _FakeResponse(
        ok=False,
        status_code=500,
        reason="Server Error",
        json_exc=ValueError("bad json"),
    )
    assert connector._handle_response_error(cast(requests.Response, response_500)) is True

    response_401 = _FakeResponse(
        ok=False,
        status_code=401,
        reason="Unauthorized",
        json_data={"message": "auth failed", "number": 1},
    )
    assert connector._handle_response_error(cast(requests.Response, response_401)) is True
    connector.log.assert_any_call(
        message="Request to BeyondTrust API failed with status 401 - Unauthorized",
        level="critical",
    )


def test_fetch_events_not_implemented(data_storage):
    connector = _BaseConnectorForTests(module=_build_module(), data_path=data_storage)
    with pytest.raises(NotImplementedError):
        BeyondTrustBaseConnector.fetch_events(connector)


def test_next_batch_no_events_and_no_sleep_branch(data_storage):
    connector = _BaseConnectorForTests(module=_build_module(), data_path=data_storage, batches=[[]])
    connector.log = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    connector.configuration = BeyondTrustPRAPlatformConfiguration(intake_key="intake_key", frequency=2)

    with pytest.MonkeyPatch.context() as m:
        times = iter([0.0, 5.0])
        m.setattr("beyondtrust_modules.connector_base.time.time", lambda: next(times, 5.0))
        sleep_mock = MagicMock()
        m.setattr("beyondtrust_modules.connector_base.time.sleep", sleep_mock)
        connector.next_batch()
        sleep_mock.assert_not_called()

    connector.log.assert_any_call(message="No events to forward", level="info")
