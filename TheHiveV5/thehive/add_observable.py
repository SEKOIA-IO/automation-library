from typing import Any, Optional, List

from sekoia_automation.action import Action
from thehive4py.types.observable import OutputObservable

# Example of multiple observables tobe added to an alert
#observables = [
#    {"dataType": "ip", "data": "192.168.1.100"},
#    {"dataType": "domain", "data": "phishing-site.com"},
#    {"dataType": "url", "data": "http://malicious.example/path"}
#]

from .thehiveconnector import TheHiveConnector

class TheHiveCreateObservableV5(Action):
    #def run(self, arguments: dict[str, Any]) -> Optional[OutputAlert]:
    def run(self, arguments: dict[str, Any]) -> Optional[OutputObservable]:
        """ api = TheHiveApi(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
        ) """
        api = TheHiveConnector(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
        )

        #arg_sekoia_server = arguments.get("sekoia_base_url", "https://app.sekoia.io")
        arg_alert_id = arguments["alert_id"]
        arg_observables = arguments["observables"]

        try:
            result = api.alert_add_observables(arg_alert_id, arg_observables)
            #print("Observables added:", result)
            return result
        except Exception as e:
            print("Error:", e)

        return None
