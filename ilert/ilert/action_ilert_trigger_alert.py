# third parties
import requests
from requests import Response
from sekoia_automation.action import Action

# internals
from ilert.constants import DEFAULT_EVENTS_URL
from ilert.helpers import requests_retry_session


class IlertTriggerAlertAction(Action):
    """
    Action to trigger an alert on an ilert Service
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
        alert_info = self._get_alert(
            alert_uuid=arguments["alert_uuid"],
            api_key=arguments["api_key"],
            base_url=arguments["base_url"],
        )

        integration_key = self.module.configuration["integration_key"]
        base_events_url = self.module.configuration.get("integration_url", DEFAULT_EVENTS_URL)
        url = f"{base_events_url}/{integration_key}"

        response: Response = requests_retry_session().post(
            url,
            json=alert_info,
        )
        response.raise_for_status()

        return alert_info
