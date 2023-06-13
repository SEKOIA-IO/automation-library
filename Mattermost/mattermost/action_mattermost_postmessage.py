# natives

# third parties
import requests
from requests import Response
from sekoia_automation.action import Action


class MattermostPostMessageAction(Action):
    """
    Action to post an arbitrary message on a channel on Mattermost
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments) -> dict:
        hook_url: str = self.module.configuration.get("hook_url")

        text: str = arguments["message"]
        channel: str = arguments.get("channel")
        username: str | None = arguments.get("username")

        params: dict = {
            "text": text,
            "channel": channel,
            "username": username,
            "icon_url": "https://app.sekoia.io/user/favicon.ico",
        }

        response: Response = requests.post(hook_url, json=params)
        response.raise_for_status()

        return params
