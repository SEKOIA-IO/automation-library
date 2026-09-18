from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import orjson
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
    configuration: BeyondTrustPRAPlatformConfiguration

    def __init__(self, *args, batches=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._batches = batches if batches is not None else []

    def fetch_events(self):
        for batch in self._batches:
            yield batch


def _build_module() -> BeyondTrustModule:
    module = BeyondTrustModule()
    module.configuration = cast(
        Any,
        BeyondTrustModuleConfiguration(
            base_url="https://tenant.beyondtrustcloud.com",
            client_id="client_1",
            client_secret="SECRET",
        ).model_dump(),
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
    connector.log.assert_any_call(
        message="Request to BeyondTrust API failed with status 500 - Server Error",
        level="error",
    )

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
        error_message="auth failed",
        error_number=1,
    )


def test_handle_response_error_non_critical_with_structured_payload(data_storage):
    connector = _BaseConnectorForTests(module=_build_module(), data_path=data_storage)
    connector.log = MagicMock()

    response_429 = _FakeResponse(
        ok=False,
        status_code=429,
        reason="Too Many Requests",
        json_data={"message": "ratelimited", "number": 99},
    )

    assert connector._handle_response_error(cast(requests.Response, response_429)) is True
    connector.log.assert_called_once_with(
        message="Request to BeyondTrust API failed with status 429 - Too Many Requests",
        level="error",
        error_message="ratelimited",
        error_number=99,
    )


def test_handle_response_error_ok_response_does_not_log(data_storage):
    connector = _BaseConnectorForTests(module=_build_module(), data_path=data_storage)
    connector.log = MagicMock()

    response_ok = _FakeResponse(ok=True, status_code=200, reason="OK")
    assert connector._handle_response_error(cast(requests.Response, response_ok)) is False
    connector.log.assert_not_called()


def test_fetch_events_not_implemented(data_storage):
    connector = _BaseConnectorForTests(module=_build_module(), data_path=data_storage)
    with pytest.raises(NotImplementedError):
        BeyondTrustBaseConnector.fetch_events(connector)


def test_next_batch_no_events_and_no_sleep_branch(data_storage):
    connector = _BaseConnectorForTests(module=_build_module(), data_path=data_storage, batches=[[]])
    connector.log = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    connector.configuration = cast(
        Any,
        BeyondTrustPRAPlatformConfiguration(intake_key="intake_key", frequency=2).model_dump(),
    )

    with pytest.MonkeyPatch.context() as m:
        times = iter([0.0, 5.0])
        m.setattr("beyondtrust_modules.connector_base.time.time", lambda: next(times, 5.0))
        sleep_mock = MagicMock()
        m.setattr("beyondtrust_modules.connector_base.time.sleep", sleep_mock)
        connector.next_batch()
        sleep_mock.assert_not_called()

    connector.log.assert_any_call(message="No events to forward", level="info")


def _patch_descriptors(monkeypatch, files):
    """Replace the on-disk descriptor scan with an in-memory set.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        files: mapping of ``filename -> content`` where content is a dict
            (serialized as JSON), raw ``bytes``, or an ``Exception`` instance to
            raise when the descriptor is read.
    """
    paths = [Path(name) for name in files]

    def fake_glob(self, pattern):
        assert pattern == "*.json"
        return list(paths)

    def fake_read_bytes(self):
        content = files[self.name]
        if isinstance(content, Exception):
            raise content
        if isinstance(content, (bytes, bytearray)):
            return bytes(content)
        return orjson.dumps(content)

    monkeypatch.setattr("beyondtrust_modules.connector_base.Path.glob", fake_glob)
    monkeypatch.setattr("beyondtrust_modules.connector_base.Path.read_bytes", fake_read_bytes)


def _connector_with_command(data_storage, command):
    # scalability_labels only depends on module.command and the descriptor files,
    # so no connector configuration is needed here.
    module = _build_module()
    module._command = command
    return _BaseConnectorForTests(module=module, data_path=data_storage)


def test_scalability_labels_prefers_connector_descriptor(data_storage, monkeypatch):
    """When both descriptors match the command, the connector_* one wins."""
    _patch_descriptors(
        monkeypatch,
        {
            "trigger_beyondtrust_pra.json": {
                "docker_parameters": "run_connector",
                "labels": {"scalable_horizontally": True, "scalable_vertically": True},
            },
            "connector_beyondtrust_pra.json": {
                "docker_parameters": "run_connector",
                "labels": {"scalable_horizontally": False, "scalable_vertically": True},
            },
        },
    )

    connector = _connector_with_command(data_storage, "run_connector")

    # Values come from the connector_* descriptor and are normalized to lowercase strings.
    assert connector.scalability_labels == {
        "scalable_horizontally": "false",
        "scalable_vertically": "true",
    }


def test_scalability_labels_falls_back_to_trigger_descriptor(data_storage, monkeypatch):
    """The trigger_* descriptor is used when the connector_* one does not provide labels."""
    _patch_descriptors(
        monkeypatch,
        {
            # connector_* matches the command but carries no labels -> keep looking.
            "connector_beyondtrust_pra.json": {"docker_parameters": "run_connector"},
            "trigger_beyondtrust_pra.json": {
                "docker_parameters": "run_connector",
                "labels": {"scalable_horizontally": True, "scalable_vertically": False},
            },
        },
    )

    connector = _connector_with_command(data_storage, "run_connector")

    assert connector.scalability_labels == {
        "scalable_horizontally": "true",
        "scalable_vertically": "false",
    }


def test_scalability_labels_default_when_no_descriptor_matches(data_storage, monkeypatch):
    """A command with no matching descriptor yields the non-scalable default."""
    _patch_descriptors(
        monkeypatch,
        {
            "connector_beyondtrust_pra.json": {
                "docker_parameters": "other_connector",
                "labels": {"scalable_horizontally": True, "scalable_vertically": True},
            },
        },
    )

    connector = _connector_with_command(data_storage, "run_connector")

    assert connector.scalability_labels == {
        "scalable_horizontally": "false",
        "scalable_vertically": "false",
    }


def test_scalability_labels_skips_invalid_descriptors(data_storage, monkeypatch):
    """Unreadable / malformed descriptors are skipped without breaking resolution."""
    _patch_descriptors(
        monkeypatch,
        {
            # connector_* sorted first but cannot be parsed -> skipped.
            "connector_beyondtrust_pra.json": orjson.JSONDecodeError("boom", "", 0),
            "trigger_beyondtrust_pra_broken.json": OSError("cannot read"),
            "trigger_beyondtrust_pra.json": {
                "docker_parameters": "run_connector",
                "labels": {"scalable_horizontally": False, "scalable_vertically": True},
            },
        },
    )

    connector = _connector_with_command(data_storage, "run_connector")

    assert connector.scalability_labels == {
        "scalable_horizontally": "false",
        "scalable_vertically": "true",
    }


def test_scalability_labels_default_when_only_matching_descriptor_is_invalid(data_storage, monkeypatch):
    """If the only matching descriptor is invalid, fall back to the default."""
    _patch_descriptors(
        monkeypatch,
        {
            "connector_beyondtrust_pra.json": orjson.JSONDecodeError("boom", "", 0),
        },
    )

    connector = _connector_with_command(data_storage, "run_connector")

    assert connector.scalability_labels == {
        "scalable_horizontally": "false",
        "scalable_vertically": "false",
    }


def test_scalability_labels_default_when_no_command(data_storage, monkeypatch):
    """Without a command, no descriptor is read and the default is returned."""
    glob_calls = []

    def fake_glob(self, pattern):
        glob_calls.append(pattern)
        return []

    monkeypatch.setattr("beyondtrust_modules.connector_base.Path.glob", fake_glob)
    # module.command falls back to sys.argv when _command is unset; neutralize it
    # so the "no command" branch is genuinely exercised.
    monkeypatch.setattr("sys.argv", ["pytest"])
    monkeypatch.delenv("SYMPHONY_RUNTIME", raising=False)

    connector = _connector_with_command(data_storage, None)

    assert connector.scalability_labels == {
        "scalable_horizontally": "false",
        "scalable_vertically": "false",
    }
    # The descriptor directory must not even be scanned when there is no command.
    assert glob_calls == []
