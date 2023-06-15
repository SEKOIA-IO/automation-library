# natives

import requests

# third parties
from colour import Color
from requests import Response
from sekoia_automation.action import Action


class MattermostPostAlertAction(Action):
    """
    Action to post an alert on a channel on Mattermost
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_alert(self, alert_uuid: str, api_key: str, base_url: str) -> dict:
        """
        Returns the definition of an alert
        """

        url = f"{base_url}v1/sic/alerts/{alert_uuid}"

        response: Response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
        return response.json()

    def run(self, arguments) -> dict:
        alert_uuid = arguments["alert_uuid"]

        alert_info = self._get_alert(
            alert_uuid=alert_uuid,
            api_key=arguments["api_key"],
            base_url=arguments["base_url"],
        )

        hook_url: str = self.module.configuration.get("hook_url")
        channel: str = arguments.get("channel")

        # the color value depends on the urgency of the alert
        alert_urgency: int = alert_info["urgency"]["current_value"]
        left_border_color: str = list(Color("green").range_to(Color("red"), 101))[alert_urgency].hex

        pretext = arguments.get("pretext")
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
