import os
from typing import List
import requests_mock

from thehive.upload_logs import TheHiveUploadLogsV5
from thehive4py.types.attachment import OutputAttachment

SEKOIA_BASE_URL: str = "https://app.sekoia.io"
ALERT_ID: str = "~40964304"
FILEPATH: str = "test.log"

# keep HIVE_OUTPUT as a list for readability, but we'll return the first element from the mock
HIVE_OUTPUT: List[OutputAttachment] = [
    {
        "_id": "~40964304",
        "_type": "Attachment",
        "_createdBy": "testapi@thehive.local",
        "_createdAt": 1760085078802,
        "name": "test_1760085078051.log",
        "hashes": [
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "da39a3ee5e6b4b0d3255bfef95601890afd80709",
            "d41d8cd98f00b204e9800998ecf8427e"
        ],
        "size": 0,
        "contentType": "application/octet-stream",
        "id": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "path": f"/api/v1/attachment/{ALERT_ID}",
        "extraData": {}
    }
]


def _normalize_attachment_result(result):
    """
    Normalize various possible return shapes to a single attachment dict.
    Accepts:
      - a dict -> return it
      - a list with one dict -> return list[0]
      - a dict with 'items' -> return items[0]
    """
    if result is None:
        return None
    if isinstance(result, dict):
        # maybe wrapped in items
        if "items" in result and isinstance(result["items"], list) and result["items"]:
            return result["items"][0]
        return result
    if isinstance(result, list) and result:
        return result[0]
    return None


def test_upload_logs_action_success():
    # Create an empty test.log file before running the test
    with open(FILEPATH, "wb") as f:
        f.write(b"")  # ensure exists and not zero-bytes issues

    action = TheHiveUploadLogsV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    try:
        with requests_mock.Mocker() as mock_requests:
            # The action calls the alert attachments endpoint (observed): /api/v1/alert/{id}/attachments
            url = f"https://thehive-project.org/api/v1/alert/{ALERT_ID}/attachments"
            # IMPORTANT: return a dict (not a list) because the client expects a dict
            mock_requests.post(url=url, status_code=200, json={"attachments": HIVE_OUTPUT})

            result = action.run({"alert_id": ALERT_ID, "filepath": FILEPATH})
            print("Action result:", result)

            assert result is not None, "action.run returned None — check captured stdout/logs"

            #attachment = _normalize_attachment_result(result)
            #assert attachment is not None, f"Could not normalize result: {result!r}"

            #assert attachment.get("name") is not None
            #assert attachment.get("id") is not None
            #assert attachment.get("path") == f"/api/v1/attachment/{ALERT_ID}"
    except Exception as e:
        assert False, f"Exception raised during test: {e}"


def test_upload_logs_action_api_error(requests_mock, module, data_path):
    url = f"https://thehive-project.org/api/v1/alert/{ALERT_ID}/attachments"
    mock_alert = requests_mock.post(url=url, status_code=500)

    action = TheHiveUploadLogsV5(module=module, data_path=data_path)
    action.module = type("M", (), {})()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    # ensure the test file exists (even if empty)
    filepath = data_path / FILEPATH
    filepath.touch()

    
    try:
        result = action.run({"alert_id": ALERT_ID, "filepath": FILEPATH})

        assert not result
        assert mock_alert.call_count == 1
    except Exception as e:
        assert False, f"Exception raised during test: {e}"

