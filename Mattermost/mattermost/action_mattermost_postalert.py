import requests
from typing import Annotated
from uuid import UUID

# third parties
from colour import Color
from pydantic import BaseModel, Field, HttpUrl, StringConstraints, model_validator
from requests import Response
from sekoia_automation.action import Action

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MattermostPostAlertArguments(BaseModel):
    alert_uuid: str = Field(..., description="The identifier (UUID or short id) of the alert")
    api_key: NonEmptyStr = Field(..., description="The Sekoia.io API-Key to read the alert content.")
    base_url: HttpUrl = Field(..., description="Base URL of Sekoia.io api (e.g. https://api.sekoia.io/).")
    channel: str | None = None
    pretext: str | None = None

    @model_validator(mode="after")
    def validate_alert_uuid(self) -> "MattermostPostAlertArguments":
        # emptiness check
        if self.alert_uuid is None or not self.alert_uuid.strip():
            raise ValueError("The alert identifier must not be empty")

        # short id validation
        if self.alert_uuid.startswith("AL"):
            # If the identifier starts with "AL", we assume it's a short ID
            return self

        # UUID validation
        try:
            UUID(self.alert_uuid)
        except ValueError:
            raise ValueError(f"Invalid alert identifier: {self.alert_uuid}")

        return self


class MattermostPostAlertAction(Action):
    """
    Action to post an alert on a channel on Mattermost
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_alert(self, alert_uuid: str, api_key: str, base_url: HttpUrl) -> dict:
        """
        Returns the definition of an alert
        """

        url = f"{str(base_url)}v1/sic/alerts/{alert_uuid}"

        response: Response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
        return response.json()

    def run(self, arguments: MattermostPostAlertArguments) -> dict | None:
        alert_info = self._get_alert(
            alert_uuid=arguments.alert_uuid,
            api_key=arguments.api_key,
            base_url=arguments.base_url,
        )

        hook_url: str = self.module.configuration.get("hook_url")
        channel: str | None = arguments.channel

        # the color value depends on the urgency of the alert
        alert_urgency: int = alert_info["urgency"]["current_value"]
        left_border_color: str = list(Color("green").range_to(Color("red"), 101))[alert_urgency].hex

        pretext = arguments.pretext
        author_name = alert_info["entity"]["name"]
        title = alert_info["title"]
        title_link = f"https://app.sekoia.io/sic/alerts/{alert_info['short_id']}"
        fields = [
            {
                "short": True,
                "title": "Alert type",
                "value": f"{alert_info['alert_type']['category']} - {alert_info['alert_type']['value']}",
            },
            {
                "short": True,
                "title": "Urgency",
                "value": f"{alert_info['urgency']['display']} - {alert_info['urgency']['current_value']}",
            },
            {"short": True, "title": "Source", "value": alert_info.get("source")},
            {"short": True, "title": "Target", "value": alert_info["target"]},
            {"short": False, "title": "Description", "value": alert_info["details"]},
        ]

        fallback = title
        if pretext is not None:
            fallback = f"{pretext} - {fallback}"

        params: dict = {
            "channel": channel,
            "username": author_name,
            "icon_url": "https://app.sekoia.io/user/favicon.ico",
            "attachments": [
                {
                    "fallback": fallback,
                    "color": left_border_color,
                    "pretext": pretext,
                    "author_name": author_name,
                    "title": title,
                    "title_link": title_link,
                    "fields": fields,
                }
            ],
        }

        response: Response = requests.post(hook_url, json=params)
        response.raise_for_status()

        return params
