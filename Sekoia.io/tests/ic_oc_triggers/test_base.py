import importlib.util
import json
import sys
from unittest.mock import Mock, patch

import pytest
from requests import HTTPError
from websocket import WebSocketTimeoutException

from sekoiaio.triggers import base as base_module
from sekoiaio.triggers.alerts import _SEKOIANotificationBaseTrigger


@pytest.fixture
def base_trigger(module_configuration):
    base_trigger = _SEKOIANotificationBaseTrigger()
    base_trigger.module.configuration = module_configuration
    base_trigger.module._community_uuid = "cc93fe3f-c26b-4eb1-82f7-082209cf1892"
    base_trigger.log = Mock()
    base_trigger.log_exception = Mock()

    return base_trigger


def test_sekoianotificationbasetrigger_handler_dispatch_invalid_messages(base_trigger):
    invalid_messages = [
        {},
        {"event_type": "unknown_type"},
        {"event_type": "unknown-type"},
        {"event_version": "2"},
    ]

    for message in invalid_messages:
        base_trigger.handler_dispatcher(json.dumps(message))


def test_sekoianotificationbasetrigger_handler_dispatch_invalid_json(base_trigger):
    base_trigger.handler_dispatcher("dfdfg")


def test_sekoianotificationbasetrigger_liveapi_url(base_trigger):
    base_trigger.module.configuration["base_url"] = "https://app.sekoia.io"
    assert base_trigger.liveapi_url == "wss://app.sekoia.io/live/"


def test_sekoianotificationbasetrigger_liveapi_url_api(base_trigger):
    base_trigger.module.configuration["base_url"] = "https://api.sekoia.io"
    assert base_trigger.liveapi_url == "wss://app.sekoia.io/live/"


def test_sekoianotificationbasetrigger_liveapi_url_test(base_trigger):
    base_trigger.module.configuration["base_url"] = "wss://app.test.sekoia.io"
    assert base_trigger.liveapi_url == "wss://app.test.sekoia.io/live/"


def test_sekoianotificationbasetrigger_liveapi_url_other(base_trigger):
    base_trigger.module.configuration["liveapi_url"] = "wss://other"
    assert base_trigger.liveapi_url == "wss://other"


def test_sekoianotificationbasetrigger_liveapi_url_other_generated(base_trigger):
    base_trigger.module.configuration["base_url"] = "https://fra2.app.sekoia.io"
    assert base_trigger.liveapi_url == "wss://fra2.app.sekoia.io/live/"


def test_on_error(base_trigger):
    base_trigger.on_error(None, Exception())
    base_trigger.log_exception.assert_called_once()
    base_trigger.log_exception.reset_mock()
    base_trigger.on_error(None, Exception())
    base_trigger.log_exception.assert_not_called()


def test_on_open(base_trigger):
    ws = Mock()
    base_trigger.on_open(ws)
    ws.send.assert_called_with('{"action": "upgrade"}')


def test_ping(base_trigger):
    base_trigger.on_ping(None, None)
    base_trigger.log.assert_called_once()


def test_pong(base_trigger):
    base_trigger.on_pong(None, None)
    base_trigger.log.assert_called_once()


def test_run_forbidden(base_trigger, requests_mock):
    requests_mock.get("http://fake.url/api/v1/me", status_code=403)
    with pytest.raises(HTTPError):
        base_trigger.run()
    assert base_trigger._error_count == 5


def test_run(base_trigger, requests_mock):
    requests_mock.get("http://fake.url/api/v1/me", status_code=200)
    base_trigger.stop()
    try:
        base_trigger.run()
    except Exception:
        pytest.fail("Should not have raised any exception")
    base_trigger.stop()


def test_stop(base_trigger):
    base_trigger.stop()
    assert base_trigger.running is False


def test_ssl_opt_no_env(base_trigger):
    assert base_trigger.ssl_opt == {}


def test_ssl_opt_env(base_trigger, monkeypatch):
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "test")
    assert base_trigger.ssl_opt == {"ca_certs": "test"}


def test_on_message_pushes_message_and_heartbeats(base_trigger, monkeypatch):
    monkeypatch.setattr(base_trigger, "heartbeat", Mock())
    monkeypatch.setattr(base_trigger, "_message_processor", Mock())

    base_trigger.on_message(None, '{"foo": "bar"}')

    base_trigger.heartbeat.assert_called_once_with()
    base_trigger._message_processor.push_message.assert_called_once_with('{"foo": "bar"}')


@pytest.mark.parametrize(
    "message",
    [
        {"authenticated": True},
        {"metadata": {"version": 2}},
    ],
)
def test_handler_dispatcher_ignores_message(base_trigger, monkeypatch, message):
    monkeypatch.setattr(base_trigger, "handle_event", Mock(), raising=False)

    base_trigger.handler_dispatcher(json.dumps(message))

    base_trigger.handle_event.assert_not_called()


def test_handler_dispatcher_logs_empty_event_type(base_trigger, monkeypatch):
    monkeypatch.setattr(base_trigger, "handle_event", Mock(), raising=False)
    message = {"metadata": {"version": 2}}

    base_trigger.handler_dispatcher(json.dumps(message))

    base_trigger.log.assert_called_once_with("Empty event type", level="error", event=message)


def test_handler_dispatcher_forwards_v2_event(base_trigger, monkeypatch):
    monkeypatch.setattr(base_trigger, "handle_event", Mock(), raising=False)
    message = {"type": "alert", "action": "created", "metadata": {"version": 2}}

    base_trigger.handler_dispatcher(json.dumps(message))

    base_trigger.handle_event.assert_called_once_with(message)


def test_validate_api_key_retries_server_errors(base_trigger, requests_mock):
    requests_mock.get("http://fake.url/api/v1/me", [{"status_code": 502}, {"status_code": 200}])

    with patch("tenacity.nap.time"):
        base_trigger._validate_api_key("http://fake.url/", "fake_api_key")

    assert requests_mock.call_count == 2


def test_run_logs_websocket_timeouts_and_keeps_listening(base_trigger, requests_mock, monkeypatch):
    requests_mock.get("http://fake.url/api/v1/me", status_code=200)
    monkeypatch.setattr(base_trigger, "_message_processor", Mock())
    monkeypatch.setattr("sekoiaio.triggers.base.setdefaulttimeout", Mock())
    websocket = Mock()

    def run_forever(*args, **kwargs):
        if websocket.run_forever.call_count == 1:
            raise WebSocketTimeoutException("timeout")
        base_trigger.stop()

    websocket.run_forever.side_effect = run_forever
    monkeypatch.setattr("sekoiaio.triggers.base.WebSocketApp", Mock(return_value=websocket))

    base_trigger.run()

    assert websocket.run_forever.call_count == 2
    base_trigger.log.assert_any_call("The websocket timed out", level="error")
    websocket.close.assert_called_once_with()


def test_gevent_monkey_patching_when_running_as_trigger(monkeypatch):
    patch_all = Mock()
    monkeypatch.setattr("gevent.monkey.patch_all", patch_all)
    monkeypatch.setattr(sys, "argv", ["main.py", "sekoiaio_alert_created_trigger"])

    # Execute a private copy of the module to exercise its import-time code
    # without replacing the module already imported by the other tests.
    spec = importlib.util.spec_from_file_location("_sekoiaio_triggers_base_copy", base_module.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    patch_all.assert_called_once_with()
