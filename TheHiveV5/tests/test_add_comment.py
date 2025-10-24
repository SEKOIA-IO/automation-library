import requests_mock
import pytest

from thehive.add_commment import TheHiveCreateCommentV5
from thehive4py.types.comment import OutputComment
from thehive4py.errors import TheHiveError

SEKOIA_BASE_URL: str = "https://app.sekoia.io"

MESSAGE: str = "Super comment added by a bot"
ALERT_ID: str = "~00000001"

HIVE_OUTPUT: OutputComment = {
    "_id": "~00000101",
    "_type": "Comment",
    "createdBy": "testapi@thehive.local",
    "createdAt": 1760087625263,
    "message": "Super comment added by a bot",
    "isEdited": False,
    "extraData": {},
}


def test_add_comment_action_success():
    action = TheHiveCreateCommentV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    with requests_mock.Mocker() as mock_requests:
        # mock_requests.post(url="https://thehive-project.org/api/v1/alert/{ALERT_ID}/comment", status_code=200, json=HIVE_OUTPUT)
        # NOTE: use f-string to put the actual ALERT_ID in the mocked URL
        url = f"https://thehive-project.org/api/v1/alert/{ALERT_ID}/comment"
        mock_requests.post(url=url, status_code=200, json=HIVE_OUTPUT)

        result = action.run({"alert_id": ALERT_ID, "message": MESSAGE})
        assert result is not None
        assert result["message"] == MESSAGE


def test_add_comment_action_api_error(requests_mock):
    # mock_alert = requests_mock.post(url="https://thehive-project.org/api/v1/alert/{ALERT_ID}/comment", status_code=500)
    # use the pytest fixture here — again build the real URL with ALERT_ID
    url = f"https://thehive-project.org/api/v1/alert/{ALERT_ID}/comment"
    mock_alert = requests_mock.post(url=url, status_code=500)

    action = TheHiveCreateCommentV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    # When API returns 500, TheHiveError should be raised
    with pytest.raises(TheHiveError):
        action.run({"alert_id": ALERT_ID, "message": MESSAGE})

    assert mock_alert.call_count == 1
