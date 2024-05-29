from typing import Any, Optional

from sekoia_automation.action import Action
from thehive4py import TheHiveApi
from thehive4py.types.alert import InputAlert, OutputAlert
from requests import HTTPError


class TheHiveCreateAlertV5(Action):
    def run(self, arguments: dict[str, Any]) -> Optional[OutputAlert]:
        api = TheHiveApi(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
        )

        arg_alert = arguments["alert"]

        alert_type = f"{arg_alert['alert_type']['category']}/{arg_alert['alert_type']['value']}"
        if len(alert_type) > 32:
            alert_type = arg_alert["alert_type"]["category"][:32]  # limit to 32 char, max of thehive api
        link = f"https://app.sekoia.io/operations/alerts/{arg_alert['short_id']}"
        alert: InputAlert = InputAlert(
            severity=arg_alert["urgency"]["severity"] // 25 + 1,  # from 0-100 to 1-4
            date=arg_alert["created_at"] * 1000,  # date in ms for TheHive instead of sec in Sekoia
            tags=[],
            externalLink=link,
            title=arg_alert["title"],
            type=alert_type,
            source="Sekoia.io",
            sourceRef=arg_alert["short_id"],
            # add full alert type in description, add link in description
            description=f"type: {alert_type}\r\nlink: {link}\r\ndetails: {arg_alert['details']}",
        )

        try:
            response = api.alert.create(alert=alert)
            return response
        except HTTPError as e:
            self.error(str(e))
            if e.response is not None:
                self.log(f"Status code: {e.response.status_code}")
                self.log(f"Response: {e.response.text}")
        except Exception as e:
            self.error(str(e))

        return None
