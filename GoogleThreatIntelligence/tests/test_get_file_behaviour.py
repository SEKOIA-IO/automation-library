import json
import urllib.parse
import requests_mock
from googlethreatintelligence.get_file_behaviour import GTIGetFileBehaviour

HOST = "https://threatintelligence.googleapis.com/"
API_KEY = "FAKE_API_KEY"
FILE_HASH = "44d88612fea8a8f36de82e1278abb02f"

GTI_OUTPUT = {
    "behaviours": {
        "network": ["dns_query", "http_post"],
        "file": ["create_temp", "write_disk"]
    }
}


def _qs_matcher(expected_params):
    def matcher(request):
        actual = {k: v[0] if isinstance(v, list) else v for k, v in request.qs.items()}
        for key, value in expected_params.items():
            if key not in actual or actual[key] != str(value):
                return False
        return True
    return matcher


def test_get_file_behaviour_success():
    action = GTIGetFileBehaviour()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = f"/v1/files/{FILE_HASH}/behaviours"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            json=GTI_OUTPUT,
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({})
        data = json.loads(response) if isinstance(response, str) else response
        assert "behaviours" in data or (data.get("data") and "behaviours" in data.get("data"))
        assert mock_requests.call_count == 1


def test_get_file_behaviour_not_found():
    action = GTIGetFileBehaviour()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = f"/v1/files/{FILE_HASH}/behaviours"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=404,
            json={"error": {"message": "Not Found"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({})
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or data.get("success") is False
        assert mock_requests.call_count == 1


def test_get_file_behaviour_api_error():
    action = GTIGetFileBehaviour()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = f"/v1/files/{FILE_HASH}/behaviours"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=500,
            json={"error": {"message": "Internal Server Error"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({})
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or data.get("success") is False
        assert mock_requests.call_count == 1
