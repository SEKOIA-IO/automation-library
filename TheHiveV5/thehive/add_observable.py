import json
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, Field, StringConstraints
from sekoia_automation.action import Action

from .thehiveconnector import TheHiveConnector

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TheHiveCreateObservableArguments(BaseModel):
    alert_id: NonEmptyStr = Field(..., description="The Unique identifier of the alert")
    events: List[Dict[str, Any]] = Field(..., description="Events to convert to observables")
    tlp: str = Field(default="AMBER", description="Traffic Light Protocol level")
    pap: str = Field(default="AMBER", description="Permissible Actions Protocol level")
    areioc: bool = Field(default=True, description="Whether the observables are IOCs")


class TheHiveCreateObservableV5(Action):
    def run(self, arguments: TheHiveCreateObservableArguments) -> Optional[Dict[str, List]]:
        api = TheHiveConnector(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
            verify=self.module.configuration.get("verify_certificate", True),
            ca_certificate=self.module.configuration.get("ca_certificate"),
            log_fn=self.log,
        )

        arg_alert_id = arguments.alert_id
        # arg_observables = arguments["observables"]
        # Input arguments are NOT observables but a list of dicts with sekoia fields
        arg_events = json.dumps(arguments.events)
        arg_tlp = arguments.tlp
        arg_pap = arguments.pap
        arg_ioc = arguments.areioc

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
