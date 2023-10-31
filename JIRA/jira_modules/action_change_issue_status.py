from pydantic import BaseModel, Field

from .action_base import JIRAAction
from .base import JIRAModule


class JiraChangeStatusArguments(BaseModel):
    issue_key: str = Field(..., description="Issue key (e.g. 'PROJ-1')")
    status_name: str = Field(..., description="Exact name of the status (e.g. 'To Do')")


class JIRAChangeIssueStatus(JIRAAction):
    name = "Change status"
    description = "Change status of an issue"
    module: JIRAModule

    def run(self, arguments: JiraChangeStatusArguments) -> None:
        _transitions = self.get_json(
            f"issue/{arguments.issue_key}/transitions",
            params={"includeUnavailableTransitions": False},
        )
        avail_transitions = {item.get("name"): item.get("id") for item in _transitions.get("transitions", [])}
        if arguments.status_name not in avail_transitions:
            self.log(
                message="`%s` status is either not found or unreachable from current status" % arguments.status_name,
                level="error",
            )
            return None

        desired_trans_id = avail_transitions.get(arguments.status_name)

        self.post_json(
            path=f"issue/{arguments.issue_key}/transitions",
            json={"transition": {"id": desired_trans_id}},
        )
