from functools import cached_property

from pydantic import BaseModel, Field
from sekoia_automation.action import Action

from .api import JiraApi
from .base import JIRAModule


class JiraChangeStatusArguments(BaseModel):
    issue_key: str = Field(..., description="Issue key (e.g. 'PROJ-1')")
    status_name: str = Field(..., description="Exact name of the status (e.g. 'To Do')")


class JIRAChangeIssueStatus(Action):
    name = "Change status"
    description = "Change status of an issue"
    module: JIRAModule

    @cached_property
    def client(self):
        return JiraApi(
            domain=self.module.configuration.domain,
            email=self.module.configuration.email,
            api_token=self.module.configuration.api_key,
        )

    def run(self, arguments: JiraChangeStatusArguments) -> None:
        _transitions = self.client.get_json(
            f"issue/{arguments.issue_key}/transitions",
            params={"includeUnavailableTransitions": False},
        )
        avail_transitions = {item.get("name"): item.get("id") for item in _transitions.get("transitions", [])}
        if arguments.status_name not in avail_transitions:
            raise AttributeError("`%s` status is either not found or unreachable from current status")

        desired_trans_id = avail_transitions.get(arguments.status_name)

        self.client.post_json(
            path=f"issue/{arguments.issue_key}/transitions",
            json={"transition": {"id": desired_trans_id}},
        )
