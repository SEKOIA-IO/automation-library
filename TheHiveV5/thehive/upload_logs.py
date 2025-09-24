from typing import Any, Optional, List

from sekoia_automation.action import Action
from thehive4py.types.observable import OutputObservable

 # Upload logs <-> Add an observable as a log file OR add_attachment in alert
 ## See: https://docs.strangebee.com/thehive/api-docs/#tag/Observable/operation/Create%20Observable%20in%20Alert

from .thehiveconnector import TheHiveConnector

class TheHiveUploadLogsV5(Action):
    def run(self, arguments: dict[str, Any]) -> Optional[OutputObservable]:
        api = TheHiveConnector(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
        )

        #arg_sekoia_server = arguments.get("sekoia_base_url", "https://app.sekoia.io")
        arg_alert_id = arguments["alert_id"]
        arg_message = arguments["message"]
        arg_tlp = arguments["tlp"]
        arg_file = arguments["file"]

        try:
            result = api.alert_add_attachment(arg_alert_id, [arg_file])
            #print("Attachment uploaded:", result)
            return result
        except Exception as e:
            print("Error:", e)

        return None
