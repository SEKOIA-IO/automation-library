from typing import List
import requests_mock

from thehive.upload_logs import TheHiveUploadLogsV5
from thehive4py.types.attachment import OutputAttachment

SEKOIA_BASE_URL: str = "https://app.sekoia.io"

ALERT_ID: str = "~40964304"

ATTACHMENT_PATHS: List[str] = ["test.log"]

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
        "path": "/api/v1/attachment/~40964304",
        "extraData": {}
    }
]


def test_upload_logs_action_success():
    action = TheHiveUploadLogsV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(url="https://thehive-project.org/api/v1/attachment", status_code=200, json=HIVE_OUTPUT)

        result = action.run({"alert_id": ALERT_ID, "filepath": ATTACHMENT_PATHS})
        assert result is not None
        assert result["name"] is not None
        assert result["id"] is not None
        assert result["path"] == "/api/v1/attachment/"+ALERT_ID


def test_upload_logs_action_api_error(requests_mock):
    mock_alert = requests_mock.post(url="https://thehive-project.org/api/v1/attachment", status_code=500)

    action = TheHiveUploadLogsV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    result = action.run({"alert_id": ALERT_ID, "filepath": ATTACHMENT_PATHS})

    assert not result
    assert mock_alert.call_count == 1
