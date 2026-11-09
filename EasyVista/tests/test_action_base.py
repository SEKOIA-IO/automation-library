import base64
import json

import pytest
import requests

from easyvista_modules.account_validator import EasyVistaAccountValidator
from easyvista_modules.action.action_view_requests_incidents_list import ViewRequestsIncidentsList


@pytest.mark.parametrize(
    "status,payload,fragment",
    [
        (590, {"error": "The request is already suspended. Operation aborted."}, "already suspended"),
        (400, {"error": "Nothing to update"}, "Nothing to update"),
        (401, {"error": "Invalid Login / Password"}, "Authentication failed (check credentials / tenant_id)"),
        (403, {"error": "Denied"}, "Permission denied for GET"),
        (404, {"error": "Resource not found"}, "Resource not found"),
        (200, {"error": "Business error"}, "Business error"),
        (302, {}, "302"),
    ],
)
def test_shared_error_policy(make_action, requests_mock, api_url, status, payload, fragment):
    action = make_action(ViewRequestsIncidentsList)
    requests_mock.get(api_url, status_code=status, json=payload)
    assert action.run({}) is None
    message = action.error.call_args.args[0]
    assert fragment in message
    assert f"EasyVista API error {status} on GET /api/v1/00001/requests:" in message


def test_non_json_error_is_truncated(make_action, requests_mock, api_url):
    action = make_action(ViewRequestsIncidentsList)
    requests_mock.get(api_url, status_code=500, text="x" * 800)
    assert action.run({}) is None
    assert action.error.call_args.args[0].endswith("x" * 500)
    assert "x" * 501 not in action.error.call_args.args[0]


@pytest.mark.parametrize("body", ["<html>Sign in</html>", "{broken", " "])
@pytest.mark.parametrize("cls", [ViewRequestsIncidentsList, EasyVistaAccountValidator])
def test_successful_non_json_response_is_rejected(make_action, requests_mock, api_url, body, cls):
    action = make_action(cls)
    requests_mock.get(api_url, text=body)
    if cls is EasyVistaAccountValidator:
        assert action.validate() is False
    else:
        assert action.run({}) is None
    action.error.assert_called_once_with("EasyVista API returned a non-JSON response where JSON was expected")


@pytest.mark.parametrize("body", ["null", "[]", '"text"', "42", "false", ""])
def test_empty_or_non_object_get_reports_error(make_action, requests_mock, api_url, body):
    action = make_action(ViewRequestsIncidentsList)
    requests_mock.get(api_url, text=body)
    assert action.run({}) is None
    assert "empty or non-object response" in action.error.call_args.args[0]


@pytest.mark.parametrize("secret", ["sécret-value", 'secret-"quoted"', r"secret-\backslash"])
def test_590_extracts_nested_error_without_server_details(make_action, requests_mock, api_url, secret):
    action = make_action(ViewRequestsIncidentsList, password=secret)
    requests_mock.get(
        api_url,
        status_code=590,
        json={
            "message": json.dumps({"error": "Invalid ticket: " + secret, "error_code": 2013}),
            "exception": [{"class": "InternalPHPClass", "file": "/srv/vendor/internal.php"}],
        },
    )
    assert action.run({}) is None
    message = action.error.call_args.args[0]
    assert message.endswith("Invalid ticket: [REDACTED]")
    assert "InternalPHPClass" not in message and "/srv/" not in message and "error_code" not in message
    assert secret not in message and json.dumps(secret)[1:-1] not in message


@pytest.mark.parametrize("message", ["Plain API message", '{"info":"No nested error"}', "null", "[]"])
def test_590_without_nested_error_uses_only_message(make_action, requests_mock, api_url, message):
    action = make_action(ViewRequestsIncidentsList)
    requests_mock.get(api_url, status_code=590, json={"message": message, "exception": "/srv/internal.php"})
    assert action.run({}) is None
    assert action.error.call_args.args[0].endswith(message)
    assert "/srv/" not in action.error.call_args.args[0]


@pytest.mark.parametrize(
    "exception",
    [
        requests.ConnectionError("unavailable"),
        requests.Timeout("timed out"),
        requests.exceptions.SSLError("certificate rejected"),
    ],
)
def test_unreachable(make_action, requests_mock, api_url, exception):
    action = make_action(ViewRequestsIncidentsList)
    requests_mock.get(api_url, exc=exception)
    assert action.run({}) is None
    assert f"EasyVista API unreachable: {type(exception).__name__}:" in action.error.call_args.args[0]


def test_error_redacts_credentials(make_action, requests_mock, api_url):
    action = make_action(ViewRequestsIncidentsList, username="user", password="fake-password")
    basic = base64.b64encode(b"user:fake-password").decode()
    requests_mock.get(api_url, status_code=590, json={"error": f"fake-access-token fake-password {basic}"})
    action.run({})
    assert action.error.call_args.args[0].endswith("[REDACTED] [REDACTED] [REDACTED]")


@pytest.mark.parametrize("secret", ["sécret-value", 'secret-"quoted"', r"secret-\backslash"])
@pytest.mark.parametrize("field", ["message", "error"])
@pytest.mark.parametrize("nested", [False, True])
def test_json_error_redacts_decoded_strings(make_action, requests_mock, api_url, secret, field, nested):
    action = make_action(ViewRequestsIncidentsList, token=secret, password=secret)
    value = {secret: [secret, {"details": secret}, 42, False, None]} if nested else secret
    requests_mock.get(api_url, status_code=590, text=json.dumps({field: value}))
    assert action.run({}) is None
    message = action.error.call_args.args[0]
    assert secret not in message
    assert json.dumps(secret)[1:-1] not in message
    assert "[REDACTED]" in message


def test_json_error_redacts_before_truncation(make_action, requests_mock, api_url):
    secret = 'sécret-"quoted"-value'
    action = make_action(ViewRequestsIncidentsList, password=secret)
    requests_mock.get(api_url, status_code=500, text=json.dumps({"message": "x" * 480 + secret}))
    assert action.run({}) is None
    message = action.error.call_args.args[0]
    assert "sécret" not in message and "s\\u00e9cret" not in message
    assert message.endswith(("x" * 480 + "[REDACTED]")[:500])


def test_error_redacts_latin1_basic_credentials(make_action, requests_mock, api_url):
    username, password = "usér", "sécret-value"
    authorization = (
        requests.Request("GET", api_url, auth=requests.auth.HTTPBasicAuth(username, password))
        .prepare()
        .headers["Authorization"]
    )
    encoded_credentials = authorization.split(" ", 1)[1]
    action = make_action(ViewRequestsIncidentsList, use_token=False, username=username, password=password)
    requests_mock.get(api_url, status_code=590, json={"error": f"Rejected {authorization}"})

    assert action.run({}) is None
    assert requests_mock.last_request.headers["Authorization"] == authorization
    message = action.error.call_args.args[0]
    assert encoded_credentials not in message
    assert message.endswith("Rejected Basic [REDACTED]")


@pytest.mark.parametrize("username,password", [("用户", "fake-password"), ("user", "secret-🔒")])
def test_redaction_handles_credentials_outside_latin1(make_action, username, password):
    action = make_action(ViewRequestsIncidentsList, username=username, password=password, token="test-token")
    assert action.redact(f"Password {password}, token test-token") == "Password [REDACTED], token [REDACTED]"


@pytest.mark.parametrize("credential", ["token", "password", "basic"])
def test_error_redacts_credentials_before_truncation(make_action, requests_mock, api_url, credential):
    action = make_action(ViewRequestsIncidentsList, username="user", password="fake-password")
    secrets = {
        "token": "fake-access-token",
        "password": "fake-password",
        "basic": base64.b64encode(b"user:fake-password").decode(),
    }
    secret = secrets[credential]
    requests_mock.get(api_url, status_code=500, text="x" * 495 + secret + " tail")
    assert action.run({}) is None
    message = action.error.call_args.args[0]
    assert secret[:5] not in message
    assert message.endswith("x" * 495 + "[REDA")


def test_url_encoding(make_action, requests_mock):
    action = make_action(ViewRequestsIncidentsList, tenant_id="00001/extra")
    path = action.request_path("I/number?#", "documents", "doc/id ?#")
    assert path == "/requests/I%2Fnumber%3F%23/documents/doc%2Fid%20%3F%23"
    url = "https://easyvista.example/api/v1/00001%2Fextra" + path
    requests_mock.get(url, json={})
    assert action.get(path) == {}


@pytest.mark.parametrize("method", ["get", "post", "put", "delete"])
@pytest.mark.parametrize("status", [204, 400])
def test_helpers_empty_or_error(make_action, requests_mock, api_url, method, status):
    action = make_action(ViewRequestsIncidentsList)
    requests_mock.register_uri(method.upper(), api_url, status_code=status)
    assert getattr(action, method)("/requests") is None
    assert action.error.called is (status == 400 or method == "get")
