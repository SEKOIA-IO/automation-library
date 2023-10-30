from functools import cached_property

import requests
from pydantic import BaseModel, Field
from sekoia_automation.action import Action

from .api import JiraApi
from .base import JIRAModule


class JiraAddCommentArguments(BaseModel):
    issue_key: str = Field(..., description="Issue key (e.g. PROJ-1)")
    comment: str = Field(..., description="Text of a comment")


class JIRAAddCommentToIssue(Action):
    name = "Comment an issue"
    description = "Add a comment to an issue"
    module: JIRAModule

    @cached_property
    def client(self) -> JiraApi:
        return JiraApi(
            domain=self.module.configuration.domain,
            email=self.module.configuration.email,
            api_token=self.module.configuration.api_key,
        )

    def add_comment_to_issue(self, issue_key: str, comment: str) -> dict | None:
        try:
            return self.client.post_json(
                path=f"issue/{issue_key}/comment",
                json={
                    "body": {
                        "content": [
                            {
                                "content": [
                                    {
                                        "text": comment,
                                        "type": "text",
                                    }
                                ],
                                "type": "paragraph",
                            }
                        ],
                        "type": "doc",
                        "version": 1,
                    }
                },
            )

        except requests.HTTPError as error:
            status_code = error.response.status_code

            if status_code == 404:
                self.log(message="Requested issue not found", level="error")
                return None

            elif status_code == 401:
                self.log(message="Credentials are incorrect", level="error")
                return None

    def run(self, arguments: JiraAddCommentArguments) -> None:
        self.add_comment_to_issue(issue_key=arguments.issue_key, comment=arguments.comment)
