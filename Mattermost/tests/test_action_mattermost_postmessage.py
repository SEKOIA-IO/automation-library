# coding: utf-8

# natives
import json

# third parties
import requests_mock

# internals
from mattermost.action_mattermost_postmessage import MattermostPostMessageAction


def test_mattermost_postmessage_default():
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostMessageAction = MattermostPostMessageAction()
    mt.module.configuration = {"hook_url": hook_url}

    with requests_mock.Mocker() as mock:
        mock.post(hook_url, text="ok")

        sample_text: str = "symphony - mattermost_postmessage_action"
        mt.run({"message": sample_text})

        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"
        assert history[0].url == hook_url
        assert json.loads(history[0].text)["text"] == sample_text


def test_mattermost_postmessage_set_username_and_channel():
    hook_url: str = "https://my.chat.mattermost/hooks/123456"

    mt: MattermostPostMessageAction = MattermostPostMessageAction()
    mt.module.configuration = {"hook_url": hook_url}

    with requests_mock.Mocker() as mock:
        mock.post(hook_url, text="ok")

        sample_text: str = "symphony - mattermost_postmessage_action"
        channel: str = "sekoiaio---operation-center"
        username: str = "arbitrary-username"
        mt.run({"message": sample_text, "channel": channel, "username": username})

        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "POST"
        assert history[0].url == hook_url
        assert json.loads(history[0].text)["text"] == sample_text
        assert json.loads(history[0].text)["username"] == username
        assert json.loads(history[0].text)["channel"] == channel
