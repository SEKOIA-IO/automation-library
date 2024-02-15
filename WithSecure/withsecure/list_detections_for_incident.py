from pydantic import BaseModel

from withsecure.incident_operation_action import IncidentOperationAction


class ActionArguments(BaseModel):
    target: str


class ListDetectionForIncident(IncidentOperationAction):
    def run(self, arguments: ActionArguments) -> None:
        # execute the operation
        self._execute_operation_on_incident(operation_name="ListDetectionForIncident", target=arguments.target)
