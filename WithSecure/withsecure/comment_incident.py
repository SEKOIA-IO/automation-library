from pydantic import BaseModel

from withsecure.incident_operation_action import IncidentOperationAction


class ActionArguments(BaseModel):
    target: str
    comment: str


class CommentIncident(IncidentOperationAction):
    def run(self, arguments: ActionArguments):
        parameters = {}
        parameters["comment"] = arguments.comment

        # execute the operation
        self._execute_operation_on_incident(
            operation_name="CommentIncident", target=arguments.target, parameters=parameters
        )
