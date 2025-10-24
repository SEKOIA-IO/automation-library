from typing import Any, Optional
import json
from sekoia_automation.action import Action
from thehive4py.types.observable import OutputObservable

from .thehiveconnector import TheHiveConnector


class TheHiveCreateObservableV5(Action):
    def run(self, arguments: dict[str, Any]) -> Optional[OutputObservable]:
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
        return api.alert_add_observables(arg_alert_id, observables)

        return None
