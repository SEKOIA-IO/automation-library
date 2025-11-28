from typing import Any

from pydantic.v1 import BaseModel, Field

from .action_base import JIRAAction
from .base import JIRAModule


class JIRASearchIssuesArguments(BaseModel):
    jql: str | None = Field(None, description="JQL query")
    fields: list[str] | None = Field(None, description="A list of fields to return for the issue (*all by default)")
    expand: str | None = Field(None, description="Comma-separated list of additional information to include")
    properties: list[str] | None = Field(
        None, description="A list of properties to return for the issue (*all by default)"
    )
    fields_by_keys: bool = Field(
        False, description="Whether fields in `fields` are referenced by keys rather than IDs"
    )
    fail_fast: bool = Field(
        False, description="Whether to fail the request quickly in case of an error while loading fields for an issue"
    )
    reconcile_issues: list[int] | None = Field(None, description="List of IDs to reconcile")


class JIRASearchIssues(JIRAAction):
    name = "Search issues"
    description = "Find issues using provided filters"
    module: JIRAModule

    def run(self, arguments: JIRASearchIssuesArguments) -> list[Any]:
        return self.post_paginated_results(
            path="search/jql",
            result_field="issues",
            payload={
                "jql": arguments.jql,
                "fields": arguments.fields,
                "expand": arguments.expand,
                "properties": arguments.properties,
                "fieldsByKeys": arguments.fields_by_keys,
                "failFast": arguments.fail_fast,
                "reconcileIssues": arguments.reconcile_issues,
            },
        )
