from pydantic import BaseModel

from withsecure.incident_operation_action import IncidentOperationAction
from withsecure.models import RemoteOperationResponse


class ActionArguments(BaseModel):
    target: str
    status: str
    resolution: str | None = None


class UpdateStatusIncident(IncidentOperationAction):
    results_model = RemoteOperationResponse

    def run(self, arguments: ActionArguments) -> RemoteOperationResponse:
        parameters = {}
        parameters["status"] = arguments.status
        if arguments.resolution:
            parameters["resolution"] = arguments.resolution

        # execute the operation
        response = self._execute_operation_on_incident(
            operation_name="UpdateStatusIncident", target=arguments.target, parameters=parameters
        )

        return RemoteOperationResponse(
            multistatus=response.get("multistatus", []), transactionId=response["transactionId"]
        )
