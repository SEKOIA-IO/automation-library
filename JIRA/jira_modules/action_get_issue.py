from typing import Any

from pydantic.v1 import BaseModel, Field

from .action_base import JIRAAction
from .base import JIRAModule


class JIRAGetIssueArguments(BaseModel):
    issue_key: str = Field(..., description="Issue key (e.g. PROJ-1) or ID")
    fields: list[str] | None = Field(None, description="A list of fields to return for the issue (*all by default)")
    fields_by_keys: bool = Field(
        False, description="Whether fields in `fields` are referenced by keys rather than IDs"
    )
    expand: str | None = Field(None, description="Comma-separated list of additional information to include")
    properties: list[str] | None = Field(
        None, description="A list of properties to return for the issue (*all by default)"
    )
    update_view_history: bool = Field(False, description="Whether to mark the issue as recently viewed")
    fail_fast: bool = Field(
        False, description="Whether to fail the request quickly in case of an error while loading fields for an issue"
    )


class JIRAGetIssue(JIRAAction):
    name = "Get issue"
    description = "Get issue"
    module: JIRAModule

    def run(self, arguments: JIRAGetIssueArguments) -> Any:
        return self.get_json(
            path=f"issue/{arguments.issue_key}",
            params={
                "fields": arguments.fields,
                "fieldsByKeys": arguments.fields_by_keys,
                "expand": arguments.expand,
                "properties": arguments.properties,
                "updateHistory": arguments.update_view_history,
                "failFast": arguments.fail_fast,
            },
        )
