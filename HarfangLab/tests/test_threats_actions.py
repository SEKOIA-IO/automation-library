import requests_mock

from harfanglab.threat_actions import AddCommentToThreat, UpdateThreatStatus


def test_add_comment_to_threat():
    instance_url = "https://test.hurukau.io"
    api_token = "117a15380a4f434c94fbe1ea7052904e"

    action = AddCommentToThreat()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST", "https://test.hurukau.io/api/data/alert/alert/Threat/1/comment/", json={"status": "comment added"}
        )
        action.run(arguments={"id": 1, "comment": "Some comment"})


def test_update_threat_status():
    instance_url = "https://test.hurukau.io"
    api_token = "117a15380a4f434c94fbe1ea7052904e"

    action = UpdateThreatStatus()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "PATCH",
            "https://test.hurukau.io/api/data/alert/alert/Threat/status/",
            json={"status": "1 threats updated"},
        )

        action.run(arguments={"threat_ids": [1, 2], "new_status": "new", "update_by_query": False})
