import json
from functools import cached_property
from typing import cast

from pydantic import BaseModel, Field

from .action_base import JIRAAction
from .base import JIRAModule


class JiraCreateIssueArguments(BaseModel):
    project_key: str = Field(..., description="Project key (e.g. 'PRJ')")
    summary: str = Field(..., description="Summary of an issue (e.g. 'Fix a bug')")
    issue_type: str = Field(..., description="Issue type (e.g. 'Task')")
    description: dict | None = Field(None, description="Description text in ADF (Atlassian Document Format)")
    due_date: str | None = Field(None, description="Due date (e.g. '2023-10-31')'")
    labels: str | None = Field(None, description="Comma-separated labels (e.g. 'devops,support')")
    assignee: str | None = Field(None, description="Exact display name of an assignee (e.g. John Doe)")
    reporter: str | None = Field(None, description="Exact display name of a reporter (e.g. Jane Doe)")
    priority: str | None = Field(None, description="Issue priority (e.g. Highest)")
    parent_key: str | None = Field(None, description="Key of a parent issue (e.g. PRJ-1)")
    custom_fields: dict | None = Field(None, description="""JSON with custom fields (e.g. {"Some Field": "2"})""")


class JiraCreateIssueRequest:
    def __init__(self, action: "JIRACreateIssue", arguments: JiraCreateIssueArguments) -> None:
        self.action = action
        self.args = arguments

        self._field_name_to_id: dict = cast(dict, None)
        self._field_name_to_type = cast(dict, None)
        self._field_allowed_values = cast(dict, None)
        self._field_item_type = cast(dict, None)

    @cached_property
    def user_name_to_id(self) -> dict:
        all_users = self.action.get_paginated_results(path="users/search", result_field=None)
        user_name_to_id = {user.get("displayName"): user.get("accountId") for user in all_users}
        return user_name_to_id

    @cached_property
    def create_issue_meta(self) -> dict:
        response: dict = self.action.get_json(
            "issue/createmeta",
            params={
                "projectKeys": self.args.project_key,
                "issuetypeNames": self.args.issue_type,
                "expand": "projects.issuetypes.fields",
            },
        )
        return response

    @property
    def project_meta(self) -> dict:
        projects = self.create_issue_meta.get("projects")
        if not projects or len(projects) == 0:
            self.action.log(message="Project `%s` is not found" % self.args.project_key, level="error")
            raise ValueError

        project = projects[0]
        return project

    @property
    def project_id(self) -> str:
        return self.project_meta["id"]

    @property
    def issue_type_meta(self) -> dict:
        issues_types = self.project_meta.get("issuetypes")
        if not issues_types or len(issues_types) == 0:
            self.action.log(message="Issue type `%s` is not found " % self.args.issue_type, level="error")
            raise ValueError

        return issues_types[0]

    @property
    def issue_type_id(self) -> str:
        return self.issue_type_meta["id"]

    @property
    def fields_in_jira(self) -> dict:
        return self.issue_type_meta["fields"]

    def __process_fields(self) -> None:
        self._field_name_to_id = {}
        self._field_name_to_type = {}
        self._field_allowed_values = {}
        self._field_item_type = {}

        for field_id, field_params in self.fields_in_jira.items():
            field_name = field_params.get("name")
            self._field_name_to_id[field_name] = field_id

            schema = field_params.get("schema", {})
            self._field_name_to_type[field_name] = schema.get("type")

            if schema.get("items"):
                self._field_item_type[field_name] = schema["items"]

            allowed_values = field_params.get("allowedValues")
            if allowed_values:
                self._field_allowed_values[field_name] = {
                    item.get("name") or item.get("value"): item.get("id") for item in allowed_values
                }

    @property
    def field_name_to_id(self):
        if not self._field_name_to_id:
            self.__process_fields()

        return self._field_name_to_id

    @property
    def field_name_to_type(self):
        if not self._field_name_to_type:
            self.__process_fields()

        return self._field_name_to_type

    @property
    def field_allowed_values(self):
        if not self._field_allowed_values:
            self.__process_fields()

        return self._field_allowed_values

    @property
    def field_item_type_by_name(self):
        if not self._field_item_type:
            self.__process_fields()

        return self._field_item_type

    def fill_parent_key(self, prev_step: dict) -> None:
        if self.args.parent_key:
            if not self.issue_type_meta.get("subtask"):
                self.action.log(
                    message="Issue type `%s` could not be a sub-task" % self.args.issue_type, level="error"
                )
                raise ValueError

            prev_step["parent"] = {"key": self.args.parent_key}

    def fill_description(self, prev_step: dict) -> None:
        if self.args.description:
            prev_step["description"] = self.args.description

    def fill_due_date(self, prev_step: dict) -> None:
        if self.args.due_date:
            prev_step["duedate"] = self.args.due_date

    def fill_assignee(self, prev_step: dict) -> None:
        if self.args.assignee:
            assignee_user_id = self.user_name_to_id.get(self.args.assignee)
            if not assignee_user_id:
                self.action.log(message="User with name `%s` is not found" % self.args.assignee, level="error")
                raise ValueError

            prev_step["assignee"] = {"id": assignee_user_id}

    def fill_reporter(self, prev_step: dict) -> None:
        if self.args.reporter:
            reporter_user_id = self.user_name_to_id.get(self.args.reporter)
            if not reporter_user_id:
                self.action.log(message="User with name `%s` is not found" % self.args.assignee, level="error")
                raise ValueError

            prev_step["reporter"] = {"id": reporter_user_id}

    def fill_labels(self, prev_step: dict) -> None:
        if self.args.labels:
            prev_step["labels"] = self.args.labels.split(",")

    def fill_priority(self, prev_step: dict) -> None:
        if self.args.priority:
            priority_values = self.field_allowed_values["Priority"]
            if not priority_values or self.args.priority not in priority_values:
                self.action.log(message="Priority `%s` does not exist" % self.args.priority, level="error")
                raise ValueError

            prev_step["priority"] = {"id": priority_values[self.args.priority]}

    def fill_custom_fields(self, prev_step: dict) -> None:
        # https://support.atlassian.com/cloud-automation/docs/advanced-field-editing-using-json/
        if self.args.custom_fields:
            custom_fields_json = self.args.custom_fields
            for custom_field_name, custom_field_values in custom_fields_json.items():
                custom_field_type = self.field_name_to_type[custom_field_name]
                custom_field_id = self.field_name_to_id[custom_field_name]
                allowed_values = self.field_allowed_values.get(custom_field_name)

                if custom_field_type == "option":
                    if allowed_values and custom_field_values not in allowed_values:
                        self.action.log(
                            message="Incorrect value `%s` for the field `%s`"
                            % (custom_field_values, custom_field_name),
                            level="error",
                        )
                        raise ValueError

                    prev_step[custom_field_id] = {"id": allowed_values[custom_field_values]}

                elif custom_field_type == "array":
                    field_result = []
                    field_items = self.field_item_type_by_name.get(custom_field_name)

                    if allowed_values:
                        for custom_field_value in custom_field_values:
                            if custom_field_value not in allowed_values:
                                self.action.log(
                                    message="Incorrect value `%s` for the field `%s`"
                                    % (custom_field_value, custom_field_name),
                                    level="error",
                                )
                                raise ValueError

                            field_result.append({"id": allowed_values[custom_field_value]})

                    elif field_items == "user":
                        field_result = []
                        for custom_field_value in custom_field_values:
                            user_id = self.user_name_to_id.get(custom_field_value)
                            if not user_id:
                                self.action.log(
                                    message="User `%s` mentioned in the field `%s` does not exist"
                                    % (custom_field_value, custom_field_name),
                                    level="error",
                                )
                                raise ValueError

                            field_result.append({"id": user_id})

                    else:
                        field_result = [{"value": custom_field_value for custom_field_value in custom_field_values}]

                    prev_step[custom_field_id] = field_result

                else:
                    prev_step[custom_field_id] = custom_field_values

    def generate_params(self) -> dict:
        # Mandatory Fields
        params = {
            "project": {"id": self.project_id},
            "issuetype": {"id": self.issue_type_id},
            "summary": self.args.summary,
        }

        self.fill_parent_key(params)
        self.fill_description(params)
        self.fill_due_date(params)
        self.fill_assignee(params)
        self.fill_reporter(params)
        self.fill_labels(params)
        self.fill_priority(params)
        self.fill_custom_fields(params)

        return params


class JIRACreateIssue(JIRAAction):
    name = "Create an issue"
    description = "Create an issue"
    module: JIRAModule

    def run(self, arguments: JiraCreateIssueArguments) -> dict | None:
        create_issue_request = JiraCreateIssueRequest(action=self, arguments=arguments)
        params = create_issue_request.generate_params()

        response = self.post_json(
            "issue",
            json={"fields": params},
        )

        if "key" in response:
            return {"issue_key": response.get("key")}

        return {}
