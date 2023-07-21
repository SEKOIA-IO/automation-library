# natives

# third parties
import requests
from requests import Response
from sekoia_automation.action import Action

# internals
from pagerduty.constants import DEFAULT_EVENTSAPIV2_URL
from pagerduty.helpers import requests_retry_session, urgency_to_pagerduty_severity


class PagerDutyTriggerAlertAction(Action):
    """
    Action to trigger an alert on a PagerDuty Service
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

        pagerduty_payload = {
            "payload": {
                "summary": alert_info["title"],
                "source": alert_info["entity"]["name"],
                "severity": urgency_to_pagerduty_severity(alert_info["urgency"]["current_value"]),
                "class": f"{alert_info['alert_type']['category']} - {alert_info['alert_type']['value']}",
                "custom_details": {
                    "source": alert_info.get("source"),
                    "target": alert_info["target"],
                    "details": alert_info["details"],
                },
            },
            "routing_key": self.module.configuration["integration_key"],
            "dedup_key": alert_info["short_id"],
            "images": [
                {
                    "src": "https://app.sekoia.io/assets/logos/sekoiaio-black.svg",
                    "href": "https://app.sekoia.io/",
                    "alt": "Sekoia.io",
                }
            ],
            "links": [
                {
                    "href": f"https://app.sekoia.io/sic/alerts/{alert_info['short_id']}",
                    "text": "Alert details",
                }
            ],
            "event_action": "trigger",
            "client": "Sekoia.io Security Service",
            "client_url": "https://app.sekoia.io",
        }

        response: Response = requests_retry_session().post(
            self.module.configuration.get("integration_url", DEFAULT_EVENTSAPIV2_URL),
            json=pagerduty_payload,
        )
        response.raise_for_status()

        # replace integration key from payload before returning it
        pagerduty_payload["routing_key"] = "filtered-out-for-security"

        return pagerduty_payload
