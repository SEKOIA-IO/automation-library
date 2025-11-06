import json
import urllib.parse
import requests_mock
from googlethreatintelligence.scan_url import GTIScanURL

HOST = "https://threatintelligence.googleapis.com/"
API_KEY = "FAKE_API_KEY"
URL = "https://example.com/malicious"

GTI_OUTPUT = {"analysis_id": "url-anal-777", "status": "queued"}


def _qs_matcher(expected_params):
    def matcher(request):
        actual = {k: v[0] if isinstance(v, list) else v for k, v in request.qs.items()}
        for key, value in expected_params.items():
            if key not in actual or actual[key] != str(value):
                return False
        return True
    return matcher


def test_scan_url_success():
    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = "/v1/urls:scan"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            urllib.parse.urljoin(HOST, uri),
            json=GTI_OUTPUT,
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"url": URL})
        data = json.loads(response) if isinstance(response, str) else response
        assert data.get("analysis_id") == "url-anal-777"
        assert mock_requests.call_count == 1


def test_scan_url_not_found():
    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = "/v1/urls:scan"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            urllib.parse.urljoin(HOST, uri),
            status_code=404,
            json={"error": {"message": "Not Found"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"url": URL})
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or data.get("success") is False
        assert mock_requests.call_count == 1


def test_scan_url_api_error():
    action = GTIScanURL()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = "/v1/urls:scan"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            urllib.parse.urljoin(HOST, uri),
            status_code=500,
            json={"error": {"message": "Internal Server Error"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"url": URL})
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or data.get("success") is False
        assert mock_requests.call_count == 1
