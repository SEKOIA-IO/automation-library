from typing import Any, Dict
import requests_mock
import json
import urllib.parse

from googlethreatintelligence.get_ioc_report import GTIIoCReport

# === Test constants ===
HOST = "https://threatintelligence.googleapis.com/"
API_KEY = "FAKE_API_KEY"
IP = "8.8.8.8"

GTI_OUTPUT: dict[str, Any] = {
    "threat": {
        "indicator": IP,
        "confidence": "HIGH",
        "threat_types": ["MALWARE", "C2"],
        "last_seen": "2025-11-01T12:34:56Z"
    }
}


def _qs_matcher(expected_params: Dict[str, Any]):
    """
    Return a requests_mock additional_matcher that checks query params in request.qs
    """
    def matcher(request):
        actual = {k: v[0] if isinstance(v, list) else v for k, v in request.qs.items()}
        for key, value in expected_params.items():
            if key not in actual or actual[key] != str(value):
                return False
        return True
    return matcher


def test_get_ioc_report_action_success():
    """Test successful GTIIoCReport action."""
    action = GTIIoCReport()
    action.module.configuration = {
        "api_key": API_KEY,
        "host": HOST.rstrip("/")
    }

    uri = f"/v1/ipAddresses/{IP}"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            json=GTI_OUTPUT,
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        # Execute the action
        response = action.run({"ip": IP})

        assert response is not None

        # Convert to dict if returned as string
        data = json.loads(response) if isinstance(response, str) else response

        print("Result structure:", json.dumps(data, indent=2))

        assert data["threat"]["indicator"] == IP
        assert data["threat"]["confidence"] == "HIGH"
        assert mock_requests.call_count == 1


def test_get_ioc_report_action_not_found():
    """Test GTIIoCReport action when resource not found (404)."""
    action = GTIIoCReport()
    action.module.configuration = {
        "api_key": API_KEY,
        "host": HOST.rstrip("/")
    }

    uri = f"/v1/ipAddresses/{IP}"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=404,
            json={"error": {"code": 404, "message": "Not Found"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"ip": IP})

        print("Error response:", response)

        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or "message" in data
        assert mock_requests.call_count == 1


def test_get_ioc_report_action_api_error():
    """Test GTIIoCReport action on API internal server error."""
    action = GTIIoCReport()
    action.module.configuration = {
        "api_key": API_KEY,
        "host": HOST.rstrip("/")
    }

    uri = f"/v1/ipAddresses/{IP}"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=500,
            json={"error": {"message": "Internal Server Error"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"ip": IP})

        print("500 response:", response)

        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or "Error" in str(data)
        assert mock_requests.call_count == 1
