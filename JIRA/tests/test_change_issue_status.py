import time
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests.exceptions
import requests_mock

from jira_modules.action_change_issue_status import JIRAChangeIssueStatus, JiraChangeStatusArguments
from jira_modules.base import JIRAModule


@pytest.fixture
def action():
    module = JIRAModule()

    action = JIRAChangeIssueStatus(module)
    action.log = MagicMock()

    action.module.configuration = {
        "domain": "https://test.atlassian.net",
        "email": "john.doe@gmail.com",
        "api_key": "my-client-secret",
    }

    return action


@pytest.fixture
def transitions_1():
    return {
        "transitions": [
            {
                "id": "2",
                "name": "Close Issue",
                "to": {
                    "self": "https://test.atlassian.net/rest/api/3/status/10000",
                    "description": "The issue is currently being worked on.",
                    "iconUrl": "https://test.atlassian.net/images/icons/progress.gif",
                    "name": "In Progress",
                    "id": "10000",
                    "statusCategory": {
                        "self": "https://test.atlassian.net/rest/api/3/statuscategory/1",
                        "id": 1,
                        "key": "in-flight",
                        "colorName": "yellow",
                        "name": "In Progress",
                    },
                },
                "hasScreen": False,
                "isGlobal": False,
                "isInitial": False,
                "isAvailable": True,
                "isConditional": False,
                "fields": {
                    "summary": {
                        "required": False,
                        "schema": {
                            "type": "array",
                            "items": "option",
                            "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect",
                            "customId": 10001,
                        },
                        "name": "My Multi Select",
                        "key": "field_key",
                        "hasDefaultValue": False,
                        "operations": ["set", "add"],
                        "allowedValues": ["red", "blue"],
                        "defaultValue": "red",
                    }
                },
            },
            {
                "id": "711",
                "name": "QA Review",
                "to": {
                    "self": "https://test.atlassian.net/rest/api/3/status/5",
                    "description": "The issue is closed.",
                    "iconUrl": "https://test.atlassian.net/images/icons/closed.gif",
                    "name": "Closed",
                    "id": "5",
                    "statusCategory": {
                        "self": "https://test.atlassian.net/rest/api/3/statuscategory/9",
                        "id": 9,
                        "key": "completed",
                        "colorName": "green",
                    },
                },
                "hasScreen": False,
                "fields": {
                    "summary": {
                        "required": False,
                        "schema": {
                            "type": "array",
                            "items": "option",
                            "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect",
                            "customId": 10001,
                        },
                        "name": "My Multi Select",
                        "key": "field_key",
                        "hasDefaultValue": False,
                        "operations": ["set", "add"],
                        "allowedValues": ["red", "blue"],
                        "defaultValue": "red",
                    },
                    "colour": {
                        "required": False,
                        "schema": {
                            "type": "array",
                            "items": "option",
                            "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect",
                            "customId": 10001,
                        },
                        "name": "My Multi Select",
                        "key": "field_key",
                        "hasDefaultValue": False,
                        "operations": ["set", "add"],
                        "allowedValues": ["red", "blue"],
                        "defaultValue": "red",
                    },
                },
            },
        ]
    }


def test_change_status(action: JIRAChangeIssueStatus, transitions_1):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/issue/PRJ-1/transitions",
            json=transitions_1,
        )
        mock.register_uri(
            "POST",
            "https://test.atlassian.net/rest/api/3/issue/PRJ-1/transitions",
            json={},
        )
        args = JiraChangeStatusArguments(issue_key="PRJ-1", status_name="Close Issue")
        action.run(args)


def test_change_status_incorrect_transition(action: JIRAChangeIssueStatus, transitions_1):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://test.atlassian.net/rest/api/3/issue/PRJ-1/transitions",
            json=transitions_1,
        )
        mock.register_uri(
            "POST",
            "https://test.atlassian.net/rest/api/3/issue/PRJ-1/transitions",
            json={},
        )
        args = JiraChangeStatusArguments(issue_key="PRJ-1", status_name="To Test")
        action.run(args)
