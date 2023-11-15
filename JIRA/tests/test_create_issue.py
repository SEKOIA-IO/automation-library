import json
from unittest.mock import MagicMock

import pytest
import requests_mock
from requests import HTTPError

from jira_modules.action_create_issue import JIRACreateIssue, JiraCreateIssueArguments
from jira_modules.base import JIRAModule


@pytest.fixture
def action():
    module = JIRAModule()

    action = JIRACreateIssue(module)
    action.log = MagicMock()

    action.module.configuration = {
        "domain": "https://test.atlassian.net",
        "email": "john.doe@gmail.com",
        "api_key": "my-client-secret",
    }

    return action


@pytest.fixture
def create_issue_metadata_response():
    return {
        "projects": [
            {
                "self": "https://test.atlassian.net/rest/api/3/project/ED",
                "id": "10000",
                "key": "ED",
                "name": "Edison Project",
                "avatarUrls": {
                    "16x16": "https://test.atlassian.net/secure/projectavatar?size=xsmall&pid=10000&avatarId=10011",
                    "24x24": "https://test.atlassian.net/secure/projectavatar?size=small&pid=10000&avatarId=10011",
                    "32x32": "https://test.atlassian.net/secure/projectavatar?size=medium&pid=10000&avatarId=10011",
                    "48x48": "https://test.atlassian.net/secure/projectavatar?pid=10000&avatarId=10011",
                },
                "issuetypes": [
                    {
                        "self": "https://test.atlassian.net/rest/api/3/issueType/1",
                        "id": "1",
                        "description": "An error in the code",
                        "iconUrl": "https://test.atlassian.net/images/icons/issuetypes/bug.png",
                        "name": "Bug",
                        "subtask": False,
                        "fields": {
                            "issuetype": {
                                "required": True,
                                "name": "Issue Type",
                                "key": "issuetype",
                                "hasDefaultValue": False,
                                "operations": ["set"],
                            },
                            "customfield_10036": {
                                "required": False,
                                "schema": {
                                    "type": "option",
                                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:select",
                                    "customId": 10036,
                                },
                                "name": "Some Field Name",
                                "key": "customfield_10036",
                                "hasDefaultValue": False,
                                "operations": ["set"],
                                "allowedValues": [
                                    {
                                        "self": "https://test.atlassian.net/rest/api/3/customFieldOption/10020",
                                        "value": "Option 1",
                                        "id": "10020",
                                    },
                                    {
                                        "self": "https://test.atlassian.net/rest/api/3/customFieldOption/10021",
                                        "value": "Option 2",
                                        "id": "10021",
                                    },
                                ],
                            },
                            "customfield_10037": {
                                "required": False,
                                "schema": {
                                    "type": "array",
                                    "items": "option",
                                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multicheckboxes",
                                    "customId": 10037,
                                },
                                "name": "Some Checkbox",
                                "key": "customfield_10037",
                                "hasDefaultValue": False,
                                "operations": ["add", "set", "remove"],
                                "allowedValues": [
                                    {
                                        "self": "https://test.atlassian.net/rest/api/3/customFieldOption/10022",
                                        "value": "C1",
                                        "id": "10022",
                                    },
                                    {
                                        "self": "https://test.atlassian.net/rest/api/3/customFieldOption/10023",
                                        "value": "C2",
                                        "id": "10023",
                                    },
                                ],
                            },
                            "customfield_10040": {
                                "required": False,
                                "schema": {
                                    "type": "date",
                                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:datepicker",
                                    "customId": 10040,
                                },
                                "name": "Some Date",
                                "key": "customfield_10040",
                                "hasDefaultValue": False,
                                "operations": ["set"],
                            },
                            "customfield_10043": {
                                "required": False,
                                "schema": {
                                    "type": "array",
                                    "items": "user",
                                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:people",
                                    "customId": 10043,
                                    "configuration": {"isMulti": False},
                                },
                                "name": "Some User Field",
                                "key": "customfield_10043",
                                "autoCompleteUrl": "https://test.atlassian.net/rest/api/1.0/users/picker?fieldName=customfield_10043&showAvatar=true&query=",
                                "hasDefaultValue": False,
                                "operations": ["add", "set", "remove"],
                            },
                            "priority": {
                                "required": False,
                                "schema": {"type": "priority", "system": "priority"},
                                "name": "Priority",
                                "key": "priority",
                                "hasDefaultValue": True,
                                "operations": ["set"],
                                "allowedValues": [
                                    {
                                        "self": "https://test.atlassian.net/rest/api/3/priority/1",
                                        "iconUrl": "https://test.atlassian.net/images/icons/priorities/highest.svg",
                                        "name": "Highest",
                                        "id": "1",
                                    },
                                    {
                                        "self": "https://test.atlassian.net/rest/api/3/priority/2",
                                        "iconUrl": "https://test.atlassian.net/images/icons/priorities/high.svg",
                                        "name": "High",
                                        "id": "2",
                                    },
                                    {
                                        "self": "https://test.atlassian.net/rest/api/3/priority/3",
                                        "iconUrl": "https://test.atlassian.net/images/icons/priorities/medium.svg",
                                        "name": "Medium",
                                        "id": "3",
                                    },
                                    {
                                        "self": "https://test.atlassian.net/rest/api/3/priority/4",
                                        "iconUrl": "https://test.atlassian.net/images/icons/priorities/low.svg",
                                        "name": "Low",
                                        "id": "4",
                                    },
                                    {
                                        "self": "https://test.atlassian.net/rest/api/3/priority/5",
                                        "iconUrl": "https://test.atlassian.net/images/icons/priorities/lowest.svg",
                                        "name": "Lowest",
                                        "id": "5",
                                    },
                                ],
                                "defaultValue": {
                                    "self": "https://test.atlassian.net/rest/api/3/priority/3",
                                    "iconUrl": "https://test.atlassian.net/images/icons/priorities/medium.svg",
                                    "name": "Medium",
                                    "id": "3",
                                },
                            },
                        },
                    }
                ],
            }
        ]
    }


@pytest.fixture
def get_all_users_response():
    return [
        {
            "self": "https://test.atlassian.net/rest/api/3/user?accountId=5b10a2844c20165700ede21g",
            "key": "",
            "accountId": "5b10a2844c20165700ede21g",
            "accountType": "atlassian",
            "name": "",
            "avatarUrls": {
                "48x48": "https://avatar-management--avatars.server-location.prod.public.atl-paas.net/initials/MK-5.png?size=48&s=48",
                "24x24": "https://avatar-management--avatars.server-location.prod.public.atl-paas.net/initials/MK-5.png?size=24&s=24",
                "16x16": "https://avatar-management--avatars.server-location.prod.public.atl-paas.net/initials/MK-5.png?size=16&s=16",
                "32x32": "https://avatar-management--avatars.server-location.prod.public.atl-paas.net/initials/MK-5.png?size=32&s=32",
            },
            "displayName": "John Doe",
            "active": False,
        },
        {
            "self": "https://test.atlassian.net/rest/api/3/user?accountId=5b10ac8d82e05b22cc7d4ef5",
            "key": "",
            "accountId": "5b10ac8d82e05b22cc7d4ef5",
            "accountType": "atlassian",
            "name": "",
            "avatarUrls": {
                "48x48": "https://avatar-management--avatars.server-location.prod.public.atl-paas.net/initials/AA-3.png?size=48&s=48",
                "24x24": "https://avatar-management--avatars.server-location.prod.public.atl-paas.net/initials/AA-3.png?size=24&s=24",
                "16x16": "https://avatar-management--avatars.server-location.prod.public.atl-paas.net/initials/AA-3.png?size=16&s=16",
                "32x32": "https://avatar-management--avatars.server-location.prod.public.atl-paas.net/initials/AA-3.png?size=32&s=32",
            },
            "displayName": "Jane Doe",
            "active": False,
        },
    ]


def test_create_issue(action: JIRACreateIssue, create_issue_metadata_response: dict, get_all_users_response: dict):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/issue/createmeta",
            json=create_issue_metadata_response,
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )
        mock.register_uri("POST", "https://test.atlassian.net/rest/api/3/issue", json={"key": "PRJ-1"})
        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields=None,
            description={
                "content": [
                    {"content": [{"text": "This is a description field.", "type": "text"}], "type": "paragraph"}
                ],
                "type": "doc",
                "version": 1,
            },
        )
        result = action.run(args)
        assert result is not None
        assert result.get("issue_key") == "PRJ-1"


def test_create_issue_no_project(action: JIRACreateIssue) -> None:
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/issue/createmeta",
            json={"projects": []},
        )
        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields=None,
            description=None,
        )
        with pytest.raises(ValueError):
            result = action.run(args)
            assert result is None


def test_create_issue_with_incorrect_user(
    action: JIRACreateIssue, create_issue_metadata_response: dict, get_all_users_response: dict
):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/issue/createmeta",
            json=create_issue_metadata_response,
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )
        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Ham",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields=None,
            description=None,
        )
        with pytest.raises(ValueError):
            result = action.run(args)
            assert result is None


def test_create_issue_with_non_existent_priority(
    action: JIRACreateIssue, create_issue_metadata_response: dict, get_all_users_response: dict
):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/issue/createmeta",
            json=create_issue_metadata_response,
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )
        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Major",
            parent_key=None,
            custom_fields=None,
            description=None,
        )
        with pytest.raises(ValueError):
            result = action.run(args)
            assert result is None


def test_incorrect_credentials(action: JIRACreateIssue):
    with requests_mock.Mocker() as mock:
        mock.register_uri("GET", "https://test.atlassian.net/rest/api/3/issue/createmeta", json={}, status_code=403)

        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields=None,
            description=None,
        )
        with pytest.raises(HTTPError):
            result = action.run(args)
            assert result is None


def test_custom_field_text_value(
    action: JIRACreateIssue, create_issue_metadata_response: dict, get_all_users_response: dict
):
    with requests_mock.Mocker() as mock:
        mock.register_uri("POST", "https://test.atlassian.net/rest/api/3/issue", json={"key": "PRJ-1"})
        mock.register_uri(
            "GET", "https://test.atlassian.net/rest/api/3/issue/createmeta", json=create_issue_metadata_response
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )

        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields={"Some Field Name": "Option 1"},
            description=None,
        )
        result = action.run(args)
        assert result is not None

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET", "https://test.atlassian.net/rest/api/3/issue/createmeta", json=create_issue_metadata_response
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )

        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields={"Some Field Name": "Option 3"},  # non-existent
            description=None,
        )
        with pytest.raises(ValueError):
            result = action.run(args)
            assert result is None


def test_custom_select_field_value(
    action: JIRACreateIssue, create_issue_metadata_response: dict, get_all_users_response: dict
):
    with requests_mock.Mocker() as mock:
        mock.register_uri("POST", "https://test.atlassian.net/rest/api/3/issue", json={"key": "PRJ-1"})
        mock.register_uri(
            "GET", "https://test.atlassian.net/rest/api/3/issue/createmeta", json=create_issue_metadata_response
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )

        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields={"Some Checkbox": ["C1", "C2"]},
            description=None,
        )
        result = action.run(args)
        assert result is not None

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET", "https://test.atlassian.net/rest/api/3/issue/createmeta", json=create_issue_metadata_response
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )

        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields={"Some Checkbox": ["C3", "C1"]},  # C3 does not exist
            description=None,
        )
        with pytest.raises(ValueError):
            result = action.run(args)
            assert result is None


def test_custom_user_list_field_value(
    action: JIRACreateIssue, create_issue_metadata_response: dict, get_all_users_response: dict
):
    with requests_mock.Mocker() as mock:
        mock.register_uri("POST", "https://test.atlassian.net/rest/api/3/issue", json={"key": "PRJ-1"})
        mock.register_uri(
            "GET", "https://test.atlassian.net/rest/api/3/issue/createmeta", json=create_issue_metadata_response
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )

        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields={"Some User Field": ["John Doe"]},
            description=None,
        )
        result = action.run(args)
        assert result is not None

    with requests_mock.Mocker() as mock:
        mock.register_uri("POST", "https://test.atlassian.net/rest/api/3/issue", json={"key": "PRJ-1"})
        mock.register_uri(
            "GET", "https://test.atlassian.net/rest/api/3/issue/createmeta", json=create_issue_metadata_response
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )

        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Highest",
            parent_key=None,
            custom_fields={"Some User Field": ["John D'oh"]},
            description=None,
        )
        with pytest.raises(ValueError):
            result = action.run(args)
            assert result is None
