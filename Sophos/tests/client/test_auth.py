from datetime import UTC, datetime, timedelta

import pytest
import requests
import requests_mock

from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.client.exceptions import SophosApiAuthenticationError

API_HOST = "https://api-eu.central.sophos.com"
AUTHORIZATION_URL = "https://id.sophos.com/api/v2/oauth2/token"
WHOAMI_URL = f"{API_HOST}/whoami/v1"
TENANT_ID = "00000000-0000-0000-0000-000000000000"


def token(access_token: str = "foo-token", expires_in: int = 1799) -> dict:
    return {"access_token": access_token, "token_type": "bearer", "scope": "our-scope", "expires_in": expires_in}


def whoami(id_type: str = "tenant", api_hosts: dict | None = None) -> dict:
    if api_hosts is None:
        api_hosts = {"global": "https://api.central.sophos.com", "dataRegion": "https://api-eu02.central.sophos.com"}
    return {"id": TENANT_ID, "idType": id_type, "apiHosts": api_hosts}


@pytest.fixture
def auth():
    return SophosApiAuthentication(API_HOST, AUTHORIZATION_URL, "foo", "bar")


@pytest.mark.parametrize(
    "whoami_responses, expected_api_url, expected_header",
    [
        pytest.param(
            [{"json": whoami()}],
            "https://api-eu02.central.sophos.com",
            {"X-Tenant-ID": TENANT_ID},
            id="tenant",
        ),
        pytest.param(
            [{"status_code": 502}, {"json": whoami()}],
            "https://api-eu02.central.sophos.com",
            {"X-Tenant-ID": TENANT_ID},
            id="temporary-whoami-failure",
        ),
        pytest.param(
            [{"json": whoami("organization", {"global": "https://api.central.sophos.com"})}],
            "https://api.central.sophos.com",
            {"X-Organization-ID": TENANT_ID},
            id="organization-without-data-region",
        ),
    ],
)
def test_get_credentials(auth, whoami_responses, expected_api_url, expected_header):
    with requests_mock.Mocker() as mock:
        mock.post(AUTHORIZATION_URL, json=token())
        mock.get(WHOAMI_URL, whoami_responses)

        now = datetime.now(UTC)
        credentials = auth.get_credentials()

    assert credentials.token_type == "bearer"
    assert credentials.access_token == "foo-token"
    assert now + timedelta(seconds=1750) < credentials.expires_at < now + timedelta(seconds=1850)
    assert credentials.authorization == "Bearer foo-token"
    assert credentials.tenancy_id == TENANT_ID
    assert credentials.tenancy_header == expected_header
    assert credentials.api_url == expected_api_url


def test_get_credentials_request_new_token_only_when_needed(auth):
    with requests_mock.Mocker() as mock:
        mock.get(WHOAMI_URL, json=whoami())

        # expires in 10 seconds: within the 300-second margin, renewed on the next call
        first = mock.post(AUTHORIZATION_URL, json=token("123456", expires_in=10))
        assert auth.get_credentials().authorization == "Bearer 123456"

        second = mock.post(AUTHORIZATION_URL, json=token("78910", expires_in=10000))
        assert auth.get_credentials().authorization == "Bearer 78910"

        third = mock.post(AUTHORIZATION_URL, json=token("11111", expires_in=10000))
        assert auth.get_credentials().authorization == "Bearer 78910"

    assert first.called and second.called and not third.called


@pytest.mark.parametrize("status_code", [400, 401, 403])
def test_failing_authentication(auth, status_code):
    with requests_mock.Mocker() as mock:
        mock.post(AUTHORIZATION_URL, status_code=status_code, json={"message": "Unauthorized"})
        whoami_mock = mock.get(WHOAMI_URL, json=whoami())

        with pytest.raises(SophosApiAuthenticationError) as error:
            auth.get_credentials()

    assert str(error.value) == "Authentication failed. Check your client_id and client_secret."
    assert not whoami_mock.called


@pytest.mark.parametrize("status_code", [400, 401, 403])
def test_failing_whoami(auth, status_code):
    with requests_mock.Mocker() as mock:
        mock.post(AUTHORIZATION_URL, json=token())
        mock.get(WHOAMI_URL, status_code=status_code, json={"error": "Unauthorized"})

        with pytest.raises(SophosApiAuthenticationError) as error:
            auth.get_credentials()

    assert str(error.value) == "The Whoami call failed. Check your client_id and client_secret."


@pytest.mark.parametrize(
    "token_status, whoami_status",
    [pytest.param(404, 200, id="token-not-found"), pytest.param(200, 404, id="whoami-not-found")],
)
def test_other_http_errors_are_raised(auth, token_status, whoami_status):
    with requests_mock.Mocker() as mock:
        mock.post(AUTHORIZATION_URL, status_code=token_status, json=token())
        mock.get(WHOAMI_URL, status_code=whoami_status, json=whoami())

        with pytest.raises(requests.HTTPError):
            auth.get_credentials()


def test_requests_are_authenticated(auth):
    with requests_mock.Mocker() as mock:
        mock.post(AUTHORIZATION_URL, json=token())
        mock.get(WHOAMI_URL, json=whoami())
        api = mock.get("https://api-eu02.central.sophos.com/siem/v1/events", json={})

        requests.get("https://api-eu02.central.sophos.com/siem/v1/events", auth=auth)

    assert api.last_request.headers["Authorization"] == "Bearer foo-token"
    assert api.last_request.headers["X-Tenant-ID"] == TENANT_ID
