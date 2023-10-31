from pydantic import BaseModel, Field

from .action_base import JIRAAction
from .base import JIRAModule


class JiraAddCommentArguments(BaseModel):
    issue_key: str = Field(..., description="Issue key (e.g. PROJ-1)")
    comment: str = Field(..., description="Text of a comment")


class JIRAAddCommentToIssue(JIRAAction):
    name = "Comment an issue"
    description = "Add a comment to an issue"
    module: JIRAModule

    def add_comment_to_issue(self, issue_key: str, comment: str) -> dict | None:
        return self.post_json(
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

    def run(self, arguments: JiraAddCommentArguments) -> None:
        self.add_comment_to_issue(issue_key=arguments.issue_key, comment=arguments.comment)
