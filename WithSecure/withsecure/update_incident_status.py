from pydantic import BaseModel

from withsecure.incident_operation_action import IncidentOperationAction


class ActionArguments(BaseModel):
    target: str
    status: str
    resolution: str | None = None


class UpdateStatusIncident(IncidentOperationAction):
    def run(self, arguments: ActionArguments):
        parameters = {}
        parameters["status"] = arguments.status
        if arguments.resolution:
            parameters["resolution"] = arguments.resolution

        # execute the operation
        self._execute_operation_on_incident(
            operation_name="UpdateStatusIncident", target=arguments.target, parameters=parameters
        )
