import json

import pytest
import requests

from sophos_module.client.errors import (
    describe_error,
    error_hint,
    format_http_error,
    identify_api,
    is_configuration_error,
)

XDR_URL = "https://api-eu01.central.sophos.com/xdr-query/v1/queries/runs"


def make_response(status_code: int, body=None, text: str = "", reason: str | None = "Forbidden", url: str = XDR_URL):
    response = requests.Response()
    response.status_code = status_code
    response.reason = reason
    response.url = url
    response._content = (json.dumps(body) if body is not None else text).encode()
    return response


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://id.sophos.com/api/v2/oauth2/token", ("authentication", "")),
        ("https://api.central.sophos.com/whoami/v1", ("authentication", "")),
        ("https://api-eu01.central.sophos.com/siem/v1/events", ("SIEM API", "Service Principal ReadOnly")),
        (XDR_URL, ("XDR Data Lake API", "Service Principal Forensics")),
        ("https://api.taegis.sophos.com/graphql", ("Sophos Fusion GraphQL API", "Service Principal ReadOnly")),
        (
            "https://api-eu01.central.sophos.com/endpoint/v1/endpoints/x/isolation",
            ("Endpoint API", "Service Principal Management"),
        ),
        (
            "https://api-eu01.central.sophos.com/common/v1/directory/users",
            ("Common API", "Service Principal ReadOnly"),
        ),
        ("https://api.central.sophos.com/unknown", ("Sophos API", "")),
        (None, ("Sophos API", "")),
    ],
)
def test_identify_api(url, expected):
    assert identify_api(url) == expected


@pytest.mark.parametrize(
    "response, expected",
    [
        pytest.param(
            make_response(403, {"error": "UNAUTHORIZED_ACCESS", "message": "Forbidden", "requestId": "r-1"}),
            "UNAUTHORIZED_ACCESS: Forbidden",
            id="sophos-error-without-request-id",
        ),
        pytest.param(make_response(400, {"message": "Invalid query"}), "None: Invalid query", id="message-only"),
        pytest.param(make_response(500, {"requestId": "r-1"}, reason="Server Error"), "Server Error", id="ids-only"),
        pytest.param(make_response(500, {}, reason=None), "no details", id="no-reason"),
        pytest.param(
            make_response(502, text="<html>Bad Gateway</html>", reason="Bad Gateway"), "Bad Gateway", id="html"
        ),
        pytest.param(make_response(503, ["unexpected"], reason="Unavailable"), "Unavailable", id="json-list"),
    ],
)
def test_describe_error(response, expected):
    assert describe_error(response) == expected


@pytest.mark.parametrize(
    "status_code, url, expected",
    [
        pytest.param(
            401,
            XDR_URL,
            ". Check the client_id and client_secret of the module, and that the API credential has not expired",
            id="401",
        ),
        pytest.param(
            403,
            XDR_URL,
            ". Check that the API credential has the 'Service Principal Forensics' role"
            " and that the XDR licence of the tenant is valid",
            id="403-data-lake",
        ),
        pytest.param(
            403,
            "https://api-eu01.central.sophos.com/siem/v1/events",
            ". Check that the API credential has the 'Service Principal ReadOnly' role",
            id="403-siem",
        ),
        pytest.param(
            403,
            "https://api-eu01.central.sophos.com/endpoint/v1/endpoints/x/scans",
            ". Check that the API credential has the 'Service Principal Management' role",
            id="403-endpoint",
        ),
        pytest.param(403, "https://id.sophos.com/api/v2/oauth2/token", ". Check the API credential", id="403-auth"),
        pytest.param(429, XDR_URL, ". The Sophos rate limit is reached: retried on the next cycle", id="429"),
        pytest.param(500, XDR_URL, ". Error on the Sophos side: retried on the next cycle", id="500"),
        pytest.param(503, None, ". Error on the Sophos side: retried on the next cycle", id="503"),
        pytest.param(400, XDR_URL, "", id="400"),
        pytest.param(404, XDR_URL, "", id="404"),
    ],
)
def test_error_hint(status_code, url, expected):
    assert error_hint(status_code, url) == expected


@pytest.mark.parametrize(
    "status_code, expected",
    [(401, True), (403, True), (400, False), (404, False), (429, False), (500, False), (None, False)],
)
def test_is_configuration_error(status_code, expected):
    assert is_configuration_error(status_code) is expected


def test_format_http_error():
    response = make_response(403, {"error": "UNAUTHORIZED_ACCESS", "message": "Forbidden", "correlationId": "c-1"})

    assert format_http_error("Failed to post the query", response) == (
        "Failed to post the query: status 403 - UNAUTHORIZED_ACCESS: Forbidden"
        ". Check that the API credential has the 'Service Principal Forensics' role"
        " and that the XDR licence of the tenant is valid"
    )
