import base64
from io import BytesIO
from unittest.mock import patch

import pytest
import requests
from pydantic import ValidationError
from urllib3.exceptions import NewConnectionError
from urllib3.response import HTTPResponse

from easyvista_modules.account_validator import EasyVistaAccountValidator
from easyvista_modules.action.action_update_request_incident import UpdateRequestIncident
from easyvista_modules.action.action_view_requests_incidents_list import ViewRequestsIncidentsList
from easyvista_modules.helpers import map_fields
from easyvista_modules.models import CloseRequestIncidentArguments, EasyVistaConfiguration


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


@pytest.mark.parametrize(
    "use_token,authorization",
    [(True, "Bearer fake-access-token"), (False, "Basic " + base64.b64encode(b"test-user:fake-password").decode())],
)
def test_authentication(make_action, requests_mock, api_url, use_token, authorization):
    requests_mock.get(api_url, json={"records": []})
    action = make_action(
        ViewRequestsIncidentsList, use_token=use_token, username="test-user", password="fake-password"
    )
    action.run({})
    headers = requests_mock.last_request.headers
    assert headers["Authorization"] == authorization
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"


@pytest.mark.parametrize("cls", [ViewRequestsIncidentsList, EasyVistaAccountValidator])
@pytest.mark.parametrize(
    "config,expected",
    [
        ({"token": None}, "`token` is required when `use_token` is true"),
        ({"use_token": False}, "`username` and `password` are required when `use_token` is false"),
        ({"use_token": False, "username": "user"}, "`username` and `password` are required when `use_token` is false"),
        (
            {"use_token": False, "password": "password"},
            "`username` and `password` are required when `use_token` is false",
        ),
    ],
)
def test_conditional_credentials(make_action, requests_mock, cls, config, expected):
    action = make_action(cls, **config)
    if cls is EasyVistaAccountValidator:
        assert action.validate() is False
    else:
        assert action.run({}) is None
    action.error.assert_called_once_with(expected)
    assert not requests_mock.called


@pytest.mark.parametrize("verify", [True, False])
def test_timeout_tls_and_no_redirects(make_action, requests_mock, api_url, verify):
    requests_mock.get(api_url, json={})
    action = make_action(ViewRequestsIncidentsList, verify_ssl=verify)
    with patch.object(action.client, "send", wraps=action.client.send) as send:
        action.run({})
    assert send.call_args.kwargs["verify"] is verify
    assert send.call_args.kwargs["timeout"] == 60
    assert send.call_args.kwargs["allow_redirects"] is False


def test_error_redacts_credentials(make_action, requests_mock, api_url):
    action = make_action(ViewRequestsIncidentsList, username="user", password="fake-password")
    basic = base64.b64encode(b"user:fake-password").decode()
    requests_mock.get(api_url, status_code=590, json={"error": f"fake-access-token fake-password {basic}"})
    action.run({})
    assert action.error.call_args.args[0].endswith("[REDACTED] [REDACTED] [REDACTED]")


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


def test_empty_text_filter_preserves_false():
    args = CloseRequestIncidentArguments(rfc_number="ticket", comment="", delete_actions=False)
    assert map_fields(args, {"comment": "COMMENT", "delete_actions": "DELETE_ACTIONS"}) == {"DELETE_ACTIONS": False}


@pytest.mark.parametrize("status", [502, 503, 504])
@pytest.mark.parametrize("append,attempts", [(True, 1), (False, 3)])
def test_append_updates_are_not_retried(make_action, monkeypatch, api_url, status, append, attempts):
    monkeypatch.setenv("NO_PROXY", "*")
    action = make_action(UpdateRequestIncident)
    methods = []

    def reply(conn, method, url, **kwargs):
        methods.append(method)
        return HTTPResponse(
            status=200 if method == "GET" else status,
            body=BytesIO(b'{"END_DATE_UT":""}' if method == "GET" else b'{"error":"gateway error"}'),
            headers={"Content-Type": "application/json"},
            preload_content=False,
        )

    with patch("urllib3.connectionpool.HTTPConnectionPool._make_request", side_effect=reply):
        with patch("urllib3.util.retry.time.sleep"):
            assert action.run({"rfc_number": "ticket", "description": "Evidence", "append": append}) is None
    assert methods == ["GET"] + ["PUT"] * attempts
    assert f"EasyVista API error {status}" in action.error.call_args.args[0]


def test_append_connection_failure_is_not_retried(make_action, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "*")
    action = make_action(ViewRequestsIncidentsList)
    with patch(
        "urllib3.connectionpool.HTTPConnectionPool._make_request", side_effect=NewConnectionError(None, "unreachable")
    ) as call:
        with pytest.raises(requests.ConnectionError):
            action.client.put("https://easyvista.example/requests/ticket", params={"append": "true"})
    assert call.call_count == 1


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/path",
        "https://user:pass@example.org",
        "file:///tmp/test",
        "https://example.org?token=x",
        "https://example.org#frag",
        "https://",
    ],
)
def test_base_url_rejects_non_host_urls(url):
    with pytest.raises(ValidationError):
        EasyVistaConfiguration(base_url=url, tenant_id="00001")


@pytest.mark.parametrize("use_token", [True, False])
def test_configuration_rejects_plaintext_transport(use_token):
    with pytest.raises(ValidationError, match="base_url must use HTTPS"):
        EasyVistaConfiguration(
            base_url="http://easyvista.example",
            tenant_id="00001",
            use_token=use_token,
            token="fake-token",
            username="user",
            password="fake-password",
        )


@pytest.mark.parametrize("use_token", [True, False])
def test_client_rejects_plaintext_before_sending_credentials(make_action, use_token):
    action = make_action(ViewRequestsIncidentsList, use_token=use_token, username="user", password="fake-password")
    with patch.object(requests.Session, "request") as send:
        with pytest.raises(ValueError, match="requests must use HTTPS"):
            action.client.get("http://easyvista.example/requests")
    send.assert_not_called()


@pytest.mark.parametrize("tenant_id", ["", " ", "\t\r\n", "\u2003"])
def test_configuration_rejects_empty_tenant(tenant_id):
    with pytest.raises(ValidationError):
        EasyVistaConfiguration(base_url="https://easyvista.example", tenant_id=tenant_id)


def test_configuration_preserves_tenant_leading_zeros():
    config = EasyVistaConfiguration(base_url="https://easyvista.example/", tenant_id="00001")
    assert config.tenant_id == "00001"
    assert config.base_url == "https://easyvista.example"


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
    assert action.error.called is (status == 400)


@pytest.mark.parametrize("status,valid", [(200, True), (401, False), (403, False), (404, False), (590, False)])
def test_account_validator(make_action, requests_mock, api_url, status, valid):
    requests_mock.get(api_url, status_code=status, json={"records": []} if valid else {"error": "Unavailable"})
    validator = make_action(EasyVistaAccountValidator)
    assert validator.validate() is valid
    assert requests_mock.last_request.qs == {"max_rows": ["1"], "fields": ["rfc_number"]}


@pytest.mark.parametrize(
    "method,status,attempts",
    [
        ("GET", 502, 3),
        ("PUT", 503, 3),
        ("DELETE", 504, 3),
        ("GET", 590, 1),
        ("POST", 503, 1),
        ("GET", 500, 1),
        ("GET", 429, 1),
        ("POST", 590, 1),
    ],
)
def test_http_retry_policy(make_action, monkeypatch, method, status, attempts):
    monkeypatch.setenv("NO_PROXY", "*")
    action = make_action(ViewRequestsIncidentsList)

    def reply(*args, **kwargs):
        return HTTPResponse(
            status=status,
            body=BytesIO(b'{"error":"unavailable"}'),
            headers={"Content-Type": "application/json"},
            preload_content=False,
        )

    with patch("urllib3.connectionpool.HTTPConnectionPool._make_request", side_effect=reply) as call:
        with patch("urllib3.util.retry.time.sleep"):
            response = action.client.request(method, "https://easyvista.example/requests")
    assert response.status_code == status
    assert call.call_count == attempts


@pytest.mark.parametrize("method,attempts", [("GET", 3), ("POST", 1)])
def test_connection_retries(make_action, monkeypatch, method, attempts):
    monkeypatch.setenv("NO_PROXY", "*")
    action = make_action(ViewRequestsIncidentsList)
    with patch(
        "urllib3.connectionpool.HTTPConnectionPool._make_request", side_effect=NewConnectionError(None, "unreachable")
    ) as call:
        with patch("urllib3.util.retry.time.sleep"), pytest.raises(requests.ConnectionError):
            action.client.request(method, "https://easyvista.example/requests")
    assert call.call_count == attempts


def test_read_timeouts_are_not_retried(make_action, monkeypatch):
    from urllib3.exceptions import ReadTimeoutError

    monkeypatch.setenv("NO_PROXY", "*")
    action = make_action(ViewRequestsIncidentsList)
    with patch(
        "urllib3.connectionpool.HTTPConnectionPool._make_request",
        side_effect=ReadTimeoutError(None, "/requests", "timed out"),
    ) as call:
        with pytest.raises(requests.RequestException):
            action.client.get("https://easyvista.example/requests")
    assert call.call_count == 1


def test_client_close(make_action):
    action = make_action(ViewRequestsIncidentsList)
    action.client.close()
