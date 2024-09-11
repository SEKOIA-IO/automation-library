from typing import List

from pydantic import BaseModel

from withsecure.incident_operation_action import IncidentOperationAction


class ActionArguments(BaseModel):
    target: str
    comment: str


class ItemKeys(BaseModel):
    incidentId: str
    comment: str


class CommentIncidentResponse(BaseModel):
    items: List[ItemKeys]


class CommentIncident(IncidentOperationAction):
    results_model = CommentIncidentResponse

    def run(self, arguments: ActionArguments) -> CommentIncidentResponse:
        parameters = {}
        parameters["comment"] = arguments.comment

        # execute the operation
        response = self._execute_operation_on_incident(
            operation_name="CommentIncident", target=arguments.target, parameters=parameters
        )

        return CommentIncidentResponse(items=response.get("items", {}))
