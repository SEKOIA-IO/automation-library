import pytest
import requests
import requests_mock
from usta_modules.usta_sdk import UstaClient, UstaAuthenticationError, UstaAPIError


def test_clean_params() -> None:
    """Tests the `_clean_params` static method.

    Verifies that:
    1. Lists are converted to comma-separated strings.
    2. Boolean values are preserved.
    3. `None` values are removed from the dictionary.
    """
    params = {
        "status": ["in_progress", "done"],
        "is_corporate": True,
        "empty_val": None
    }
    cleaned = UstaClient._clean_params(params)
    assert cleaned["status"] == "in_progress,done"
    assert cleaned["is_corporate"] is True
    assert "empty_val" not in cleaned


def test_iter_compromised_credentials_pagination(usta_client: UstaClient) -> None:
    """Tests the pagination logic of `iter_compromised_credentials`.

    Verifies that the generator yields results from multiple pages by following
    the 'next' URL provided in the API response.

    Args:
        usta_client (UstaClient): The SDK client fixture.
    """
    endpoint = "/security-intelligence/account-takeover-prevention/compromised-credentials-tickets"

    with requests_mock.Mocker() as m:
        # First page response (contains a 'next' link)
        m.get(
            f"{UstaClient.BASE_URL}{endpoint}",
            json={
                "results": [{"id": 1}],
                "next": f"{UstaClient.BASE_URL}/next-page"
            }
        )
        # Second page response (end of pagination)
        m.get(
            f"{UstaClient.BASE_URL}/next-page",
            json={"results": [{"id": 2}], "next": None}
        )

        results = list(usta_client.iter_compromised_credentials())

        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[1]["id"] == 2


def test_request_errors(usta_client: UstaClient) -> None:
    """Tests handling of standard HTTP error codes (401, 500) and malformed responses.

    Args:
        usta_client (UstaClient): The SDK client fixture.
    """
    with requests_mock.Mocker() as m:
        # Test 401 Authentication Error
        m.get(UstaClient.BASE_URL + "/test", status_code=401, json={"error": "unauthorized"})
        with pytest.raises(UstaAuthenticationError):
            usta_client._request("GET", "test")

        # Test 403 Authentication Error
        m.get(UstaClient.BASE_URL + "/test", status_code=403, json={"error": "unauthorized"})
        with pytest.raises(UstaAuthenticationError):
            usta_client._request("GET", "test")

        # Test 500 Server Error
        m.get(UstaClient.BASE_URL + "/error", status_code=500, text="Internal Server Error")
        with pytest.raises(UstaAPIError) as exc:
            usta_client._request("GET", "error")
        assert "Server error 500" in str(exc.value)

        # Test Invalid JSON Response (Status 200 but bad body)
        m.get(UstaClient.BASE_URL + "/bad-json", text="not a json")
        with pytest.raises(UstaAPIError) as exc:
            usta_client._request("GET", "bad-json")
        assert "Invalid JSON" in str(exc.value)


def test_request_exception(usta_client: UstaClient) -> None:
    """Tests handling of low-level network exceptions (e.g., Timeout).

    Args:
        usta_client (UstaClient): The SDK client fixture.
    """
    with requests_mock.Mocker() as m:
        m.get(UstaClient.BASE_URL + "/error", exc=requests.exceptions.ConnectTimeout)

        with pytest.raises(UstaAPIError) as exc:
            usta_client._request("GET", "error")
        assert "Network request failed" in str(exc.value)


def test_client_error_not_json(usta_client: UstaClient) -> None:
    """Tests handling of client errors (4xx) that return plain text instead of JSON.

    Ensures that the plain text error message is captured in the exception.

    Args:
        usta_client (UstaClient): The SDK client fixture.
    """
    with requests_mock.Mocker() as m:
        # 404 Error with plain text body
        m.get(UstaClient.BASE_URL + "/notfound", status_code=404, text="Not Found Plain Text")

        with pytest.raises(UstaAPIError) as exc:
            usta_client._request("GET", "notfound")

        assert "Client error 404: Not Found Plain Text" in str(exc.value)


def test_invalid_json_response(usta_client: UstaClient) -> None:
    """Tests handling of responses that claim to be JSON but are invalid.

    Args:
        usta_client (UstaClient): The SDK client fixture.
    """
    with requests_mock.Mocker() as m:
        m.get(UstaClient.BASE_URL + "/bad-json", text="this-is-not-json")

        with pytest.raises(UstaAPIError) as exc:
            usta_client._request("GET", "bad-json")
        assert "Invalid JSON received from server" in str(exc.value)