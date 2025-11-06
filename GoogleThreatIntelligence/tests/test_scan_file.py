import json
import urllib.parse
import requests_mock
from googlethreatintelligence.scan_file import GTIScanFile

HOST = "https://threatintelligence.googleapis.com/"
API_KEY = "FAKE_API_KEY"
FILE_PATH = "/tmp/testfile.bin"
FILE_HASH = "44d88612fea8a8f36de82e1278abb02f"

GTI_OUTPUT = {
    "analysis_id": "file-analysis-123",
    "status": "completed"
}


def _qs_matcher(expected_params):
    def matcher(request):
        actual = {k: v[0] if isinstance(v, list) else v for k, v in request.qs.items()}
        for key, value in expected_params.items():
            if key not in actual or actual[key] != str(value):
                return False
        return True
    return matcher


def test_scan_file_success(tmp_path, monkeypatch):
    action = GTIScanFile()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    # create a dummy file to satisfy path check
    file_local = tmp_path / "testfile.bin"
    file_local.write_bytes(b"dummy")
    uri = "/v1/files:scan"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            urllib.parse.urljoin(HOST, uri),
            json=GTI_OUTPUT,
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"file_path": str(file_local)})
        assert response is not None

        data = json.loads(response) if isinstance(response, str) else response
        assert data.get("analysis_id") == "file-analysis-123"
        assert mock_requests.call_count == 1


def test_scan_file_not_found(tmp_path):
    action = GTIScanFile()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    # path does not exist
    missing = tmp_path / "does_not_exist.bin"
    response = action.run({"file_path": str(missing)})

    assert response is not None
    data = json.loads(response) if isinstance(response, str) else response
    assert data.get("success") is False
    assert "File not found" in data.get("error", "") or "not found" in str(data.get("error", "")).lower()


def test_scan_file_api_error(tmp_path):
    action = GTIScanFile()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    # create dummy file
    file_local = tmp_path / "testfile.bin"
    file_local.write_bytes(b"dummy")
    uri = "/v1/files:scan"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            urllib.parse.urljoin(HOST, uri),
            status_code=500,
            json={"error": {"message": "Internal Server Error"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"file_path": str(file_local)})
        assert response is not None
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or data.get("success") is False
        assert mock_requests.call_count == 1
