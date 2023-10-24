import time
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests.exceptions
import requests_mock

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
                            }
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


@pytest.fixture
def get_all_priorities_response():
    return {
        "maxResults": 50,
        "startAt": 0,
        "total": 2,
        "isLast": True,
        "values": [
            {
                "self": "https://test.atlassian.net/rest/api/3/priority/3",
                "statusColor": "#009900",
                "description": "Major loss of function.",
                "iconUrl": "https://test.atlassian.net/images/icons/priorities/major.png",
                "name": "Major",
                "id": "1",
                "isDefault": True,
            },
            {
                "self": "https://test.atlassian.net/rest/api/3/priority/5",
                "statusColor": "#cfcfcf",
                "description": "Very little impact.",
                "iconUrl": "https://test.atlassian.net/images/icons/priorities/trivial.png",
                "name": "Trivial",
                "id": "2",
                "isDefault": False,
            },
        ],
    }


def test_add_comment(
    action: JIRACreateIssue,
    create_issue_metadata_response: dict,
    get_all_users_response: dict,
    get_all_priorities_response: dict,
):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/issue/createmeta",
            json=create_issue_metadata_response,
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/priority/search",
            json=get_all_priorities_response,
        )
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/users/search",
            [
                {"json": get_all_users_response},
                {"json": []},
            ],
        )
        mock.register_uri("POST", "https://test.atlassian.net/rest/api/3/issue", json={})
        args = JiraCreateIssueArguments(
            project_key="PRJ",
            summary="New Task",
            issue_type="Bug",
            due_date="2077-10-23",
            labels="dev,cloud9",
            assignee="John Doe",
            reporter="Jane Doe",
            priority="Major",
        )
        result = action.run(args)
