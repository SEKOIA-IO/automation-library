import pytest
import requests
import requests_mock

from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.client.client import BEST_EFFORT_GRAPHQL_TIMEOUT, GRAPHQL_TIMEOUT
from sophos_module.client.exceptions import SophosGraphQLError

DATA_REGION = "https://api-eu02.central.sophos.com"


@pytest.fixture
def rest_client():
    authentication = SophosApiAuthentication(
        api_host="https://api.central.sophos.com",
        authorization_url="https://id.sophos.com/api/v2/oauth2/token",
        client_id="my-id",
        client_secret="my-password",
    )
    return SophosApiClient(auth=authentication)


@pytest.fixture
def mock_rest_api():
    with requests_mock.Mocker() as mock:
        mock.post(
            "https://id.sophos.com/api/v2/oauth2/token",
            json={"access_token": "access_token", "token_type": "bearer", "expires_in": 3600},
        )
        mock.get(
            "https://api.central.sophos.com/whoami/v1",
            json={
                "id": "tenant-id",
                "idType": "tenant",
                "apiHosts": {"global": "https://api.central.sophos.com", "dataRegion": DATA_REGION},
            },
        )
        yield mock


@pytest.mark.parametrize(
    "call, method, path, expected_query, expected_body",
    [
        pytest.param(
            lambda client: client.list_siem_events({"limit": 1000, "cursor": "c"}),
            "GET",
            "/siem/v1/events",
            {"limit": ["1000"], "cursor": ["c"]},
            None,
            id="list_siem_events",
        ),
        pytest.param(
            lambda client: client.list_siem_events(),
            "GET",
            "/siem/v1/events",
            {},
            None,
            id="list_siem_events-without-parameters",
        ),
        pytest.param(
            lambda client: client.run_query({"adHocQuery": {"template": "SELECT 1"}}),
            "POST",
            "/xdr-query/v1/queries/runs",
            {},
            {"adHocQuery": {"template": "SELECT 1"}},
            id="run_query",
        ),
        pytest.param(
            lambda client: client.get_query_status("run-1"),
            "GET",
            "/xdr-query/v1/queries/runs/run-1",
            {},
            None,
            id="get_query_status",
        ),
        pytest.param(
            lambda client: client.get_query_results("run-1", page_size=7),
            "GET",
            "/xdr-query/v1/queries/runs/run-1/results",
            {"maxsize": ["1000"], "pagesize": ["7"]},
            None,
            id="get_query_results",
        ),
        pytest.param(
            lambda client: client.get_query_results("run-1", page_size=7, from_key="AAAABw=="),
            "GET",
            "/xdr-query/v1/queries/runs/run-1/results",
            {"maxsize": ["1000"], "pagesize": ["7"], "pagefromkey": ["aaaabw=="]},
            None,
            id="get_query_results-next-page",
        ),
        pytest.param(
            lambda client: client.list_endpoints({"pageSize": 500}),
            "GET",
            "/endpoint/v1/endpoints",
            {"pagesize": ["500"]},
            None,
            id="list_endpoints",
        ),
        pytest.param(
            lambda client: client.list_directory_users({"page": 2}),
            "GET",
            "/common/v1/directory/users",
            {"page": ["2"]},
            None,
            id="list_directory_users",
        ),
    ],
)
def test_rest_calls(rest_client, mock_rest_api, call, method, path, expected_query, expected_body):
    endpoint = mock_rest_api.register_uri(method, f"{DATA_REGION}{path}", json={"ok": True})

    response = call(rest_client)

    assert response.json() == {"ok": True}
    request = endpoint.last_request
    assert request.qs == expected_query
    assert request.headers["X-Tenant-ID"] == "tenant-id"
    if expected_body is not None:
        assert request.json() == expected_body


def test_get_query_results_requires_a_run_id(rest_client):
    with pytest.raises(ValueError, match="run_id is required"):
        rest_client.get_query_results(None, page_size=10)


GRAPHQL_URL = "https://api.taegis.sophos.com/graphql"


@pytest.fixture
def graphql_client():
    authentication = SophosApiAuthentication(
        api_host="https://api.central.sophos.com",
        authorization_url="https://id.sophos.com/api/v2/oauth2/token",
        client_id="my-id",
        client_secret="my-password",
    )
    return SophosApiClient(auth=authentication, graphql_api_url="https://api.taegis.sophos.com/")


@pytest.fixture
def mock_authentication():
    with requests_mock.Mocker() as mock:
        mock.post(
            "https://id.sophos.com/api/v2/oauth2/token",
            json={"access_token": "access_token", "token_type": "bearer", "expires_in": 3600},
        )
        mock.get(
            "https://api.central.sophos.com/whoami/v1",
            json={"id": "tenant-id", "idType": "tenant", "apiHosts": {"global": "https://api.central.sophos.com"}},
        )
        yield mock


def test_graphql_returns_data(graphql_client, mock_authentication):
    mock_authentication.post(GRAPHQL_URL, json={"data": {"tenant": {"id": "1"}}})

    assert graphql_client.graphql("query { tenant { id } }", {"id": "1"}) == {"tenant": {"id": "1"}}

    request = mock_authentication.last_request
    assert request.json() == {"query": "query { tenant { id } }", "variables": {"id": "1"}}
    assert request.headers["Authorization"] == "Bearer access_token"
    assert request.headers["X-Tenant-ID"] == "tenant-id"


def test_graphql_without_data(graphql_client, mock_authentication):
    mock_authentication.post(GRAPHQL_URL, json={"data": None})

    assert graphql_client.graphql("query { tenant { id } }") == {}
    assert mock_authentication.last_request.json()["variables"] == {}


def test_graphql_errors_with_http_200(graphql_client, mock_authentication):
    mock_authentication.post(
        GRAPHQL_URL,
        json={"data": None, "errors": [{"message": "failed to parse cql query", "extensions": {"code": "BAD"}}]},
    )

    with pytest.raises(SophosGraphQLError) as error:
        graphql_client.graphql("query { detectionSearch { status } }")
    assert error.value.codes == ["BAD"]


def test_graphql_http_error(graphql_client, mock_authentication):
    mock_authentication.post(GRAPHQL_URL, status_code=403, json={"message": "Forbidden"})

    with pytest.raises(requests.HTTPError):
        graphql_client.graphql("query { tenant { id } }")


@pytest.mark.parametrize(
    "best_effort, expected_timeout",
    [
        pytest.param(False, GRAPHQL_TIMEOUT, id="collection"),
        pytest.param(True, BEST_EFFORT_GRAPHQL_TIMEOUT, id="best-effort"),
    ],
)
def test_graphql_timeout(graphql_client, mock_authentication, best_effort, expected_timeout):
    mock_authentication.post(GRAPHQL_URL, json={"data": {"tenant": None}})

    graphql_client.graphql("query { tenant { id } }", best_effort=best_effort)

    assert mock_authentication.last_request.timeout == expected_timeout
    assert mock_authentication.last_request.headers["X-Tenant-ID"] == "tenant-id"


@pytest.mark.parametrize(
    "response, expected_error",
    [
        pytest.param({"status_code": 503, "json": {}}, requests.HTTPError, id="server-error"),
        pytest.param({"exc": requests.ConnectTimeout}, requests.ConnectTimeout, id="timeout"),
        pytest.param({"exc": requests.ConnectionError}, requests.ConnectionError, id="unreachable"),
    ],
)
def test_graphql_best_effort_makes_a_single_attempt(graphql_client, mock_authentication, response, expected_error):
    endpoint = mock_authentication.post(GRAPHQL_URL, **response)

    with pytest.raises(expected_error):
        graphql_client.graphql("query { tenant { id } }", best_effort=True)

    assert endpoint.call_count == 1


def test_graphql_collection_retries_server_errors(graphql_client, mock_authentication):
    endpoint = mock_authentication.post(GRAPHQL_URL, [{"status_code": 503, "json": {}}, {"json": {"data": {"a": 1}}}])

    assert graphql_client.graphql("query { a }") == {"a": 1}
    assert endpoint.call_count >= 2
