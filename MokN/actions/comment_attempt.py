from typing import Any

from pydantic import BaseModel, Field

from actions.base import MoknBaseAction


class CommentAttemptArguments(BaseModel):
    attempt_id: int = Field(..., description="Identifier of the MokN login attempt")
    comment: str = Field(..., description="Comment to add to the login attempt")


class CommentAttemptAction(MoknBaseAction):
    name = "Add comment to MokN attempt"
    description = "Add or update the comment of a specific MokN login attempt"

    def run(self, arguments: CommentAttemptArguments) -> dict[str, Any]:
        response = self.service.comment_attempt(
            attempt_id=arguments.attempt_id,
            comment=arguments.comment,
        )
        return self.build_result(response, "Comment updated successfully")
