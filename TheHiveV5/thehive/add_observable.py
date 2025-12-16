from typing import Any, Optional, Dict, List
import json
from sekoia_automation.action import Action

from .thehiveconnector import TheHiveConnector


class TheHiveCreateObservableV5(Action):
    def run(self, arguments: dict[str, Any]) -> Optional[Dict[str, List]]:
        api = TheHiveConnector(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
        )

        arg_alert_id = arguments["alert_id"]
        # arg_observables = arguments["observables"]
        # Input arguments are NOT observables but a list of dicts with sekoia fields
        arg_events = json.dumps(arguments["events"])
        arg_tlp = arguments.get("tlp", "AMBER")
        arg_pap = arguments.get("pap", "AMBER")
        arg_ioc = arguments.get("areioc", True)

        data = json.loads(arg_events)
        observables = TheHiveConnector.sekoia_to_thehive(data, arg_tlp, arg_pap, arg_ioc)
        result = api.alert_add_observables(arg_alert_id, observables)

        # Log any failures
        if result.get("failure"):
            self.log(
                f"Added {len(result['success'])} observables successfully, " f"{len(result['failure'])} failed",
                level="warning",
            )
        else:
            self.log(f"Added {len(result['success'])} observables successfully", level="info")

        return result
