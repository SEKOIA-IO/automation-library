import json
import urllib.parse
import requests_mock
from googlethreatintelligence.get_comments import GTIGetComments

HOST = "https://threatintelligence.googleapis.com/"
API_KEY = "FAKE_API_KEY"
DOMAIN = "google.com"

GTI_OUTPUT = {
    "comments": [
        {"author": "analyst1", "text": "suspicious"},
        {"author": "analyst2", "text": "confirmed"}
    ]
}


def _qs_matcher(expected_params):
    def matcher(request):
        actual = {k: v[0] if isinstance(v, list) else v for k, v in request.qs.items()}
        for key, value in expected_params.items():
            if key not in actual or actual[key] != str(value):
                return False
        return True
    return matcher


def test_get_comments_success():
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = f"/v1/domains/{DOMAIN}/comments"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            json=GTI_OUTPUT,
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"entity_type": "domains"})
        assert response is not None
        data = json.loads(response) if isinstance(response, str) else response
        assert "comments" in data or (data.get("data") and "comments" in data.get("data"))
        assert mock_requests.call_count == 1


def test_get_comments_not_found():
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = f"/v1/domains/{DOMAIN}/comments"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=404,
            json={"error": {"message": "Not Found"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"entity_type": "domains"})
        assert response is not None
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or data.get("success") is False
        assert mock_requests.call_count == 1


def test_get_comments_api_error():
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = f"/v1/domains/{DOMAIN}/comments"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=500,
            json={"error": {"message": "Internal Server Error"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"entity_type": "domains"})
        assert response is not None
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or data.get("success") is False
        assert mock_requests.call_count == 1
