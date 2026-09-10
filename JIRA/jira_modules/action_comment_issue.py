from pydantic.v1 import BaseModel, Field

from .action_base import JIRAAction
from .base import JIRAModule


class JiraAddCommentArguments(BaseModel):
    issue_key: str = Field(..., description="Issue key (e.g. PROJ-1)")
    comment: str = Field(..., description="Text of a comment")
    public: bool = False


class JIRAAddCommentToIssue(JIRAAction):
    name = "Comment an issue"
    description = "Add a comment to an issue"
    module: JIRAModule

    def add_comment_to_issue(self, issue_key: str, comment: str, public: bool = False) -> dict | None:
        payload: dict = {
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
            },
            "properties": [
                {
                    "key": "sd.public.comment",
                    "value": {"internal": not public},
                }
            ],
        }

        return self.post_json(path=f"issue/{issue_key}/comment", json=payload)

    def run(self, arguments: JiraAddCommentArguments) -> None:
        self.add_comment_to_issue(
            issue_key=arguments.issue_key,
            comment=arguments.comment,
            public=arguments.public,
        )
