import requests
from typing import Annotated

# third parties
from pydantic import BaseModel, Field, StringConstraints
from requests import Response
from sekoia_automation.action import Action

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MattermostPostMessageArguments(BaseModel):
    message: NonEmptyStr = Field(..., description="The message to post")
    channel: str | None = None
    username: str | None = None


class MattermostPostMessageAction(Action):
    """
    Action to post an arbitrary message on a channel on Mattermost
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, arguments: MattermostPostMessageArguments) -> dict | None:
        hook_url: str = self.module.configuration.get("hook_url")

        text: str = arguments.message
        channel: str | None = arguments.channel
        username: str | None = arguments.username

        params: dict = {
            "text": text,
            "channel": channel,
            "username": username,
            "icon_url": "https://app.sekoia.io/user/favicon.ico",
        }

        response: Response = requests.post(hook_url, json=params)
        response.raise_for_status()

        return params
