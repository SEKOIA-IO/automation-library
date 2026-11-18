import base64
from io import BytesIO
from unittest.mock import patch

import pytest
import requests
from urllib3.exceptions import NewConnectionError
from urllib3.response import HTTPResponse

from easyvista_modules.action.action_restart_request_incident import RestartRequestIncident
from easyvista_modules.action.action_suspend_request_incident import SuspendRequestIncident
from easyvista_modules.action.action_view_requests_incidents_list import ViewRequestsIncidentsList


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


@pytest.mark.parametrize("verify", [True, False])
def test_timeout_tls_and_no_redirects(make_action, requests_mock, api_url, verify):
    requests_mock.get(api_url, json={})
    action = make_action(ViewRequestsIncidentsList, verify_ssl=verify)
    with patch.object(action.client, "send", wraps=action.client.send) as send:
        action.run({})
    assert send.call_args.kwargs["verify"] is verify
    assert send.call_args.kwargs["timeout"] == 60
    assert send.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("append", ["true", "false", "0", "1", "", "unexpected"])
def test_append_connection_failure_is_not_retried(make_action, monkeypatch, append):
    monkeypatch.setenv("NO_PROXY", "*")
    action = make_action(ViewRequestsIncidentsList)
    with patch(
        "urllib3.connectionpool.HTTPConnectionPool._make_request", side_effect=NewConnectionError(None, "unreachable")
    ) as call:
        with pytest.raises(requests.ConnectionError):
            action.client.put("https://easyvista.example/requests/ticket", params={"append": append})
    assert call.call_count == 1


@pytest.mark.parametrize("status", [502, 503, 504])
@pytest.mark.parametrize("query", ["append=true", "append=false", "append=0", "append=", "append", "append=other"])
def test_any_append_query_disables_status_retries(make_action, monkeypatch, status, query):
    monkeypatch.setenv("NO_PROXY", "*")
    action = make_action(ViewRequestsIncidentsList)
    response = HTTPResponse(status=status, body=BytesIO(b'{"error":"gateway error"}'), preload_content=False)
    with patch("urllib3.connectionpool.HTTPConnectionPool._make_request", return_value=response) as call:
        with patch("urllib3.util.retry.time.sleep"):
            result = action.client.put("https://easyvista.example/requests/ticket?" + query)
    assert result.status_code == status
    assert call.call_count == 1


@pytest.mark.parametrize("cls", [SuspendRequestIncident, RestartRequestIncident])
def test_state_transition_is_not_retried_after_gateway_timeout(make_action, monkeypatch, cls):
    monkeypatch.setenv("NO_PROXY", "*")
    action = make_action(cls)
    responses = [
        HTTPResponse(status=504, body=BytesIO(b'{"error":"gateway timeout"}'), preload_content=False),
        HTTPResponse(status=590, body=BytesIO(b'{"error":"transition already applied"}'), preload_content=False),
    ]
    with patch("urllib3.connectionpool.HTTPConnectionPool._make_request", side_effect=responses) as call:
        with patch("urllib3.util.retry.time.sleep"):
            assert action.run({"rfc_number": "ticket"}) is None
    assert call.call_count == 1
    assert "504" in action.error.call_args.args[0]
    assert "590" not in action.error.call_args.args[0]


@pytest.mark.parametrize("use_token", [True, False])
def test_client_rejects_plaintext_before_sending_credentials(make_action, use_token):
    action = make_action(ViewRequestsIncidentsList, use_token=use_token, username="user", password="fake-password")
    with patch.object(requests.Session, "request") as send:
        with pytest.raises(ValueError, match="requests must use HTTPS"):
            action.client.get("http://easyvista.example/requests")
    send.assert_not_called()


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
