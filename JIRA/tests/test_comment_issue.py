import time
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests.exceptions
import requests_mock

from jira_modules.action_comment_issue import JiraAddCommentArguments, JIRAAddCommentToIssue
from jira_modules.base import JIRAModule


@pytest.fixture
def action():
    module = JIRAModule()

    action = JIRAAddCommentToIssue(module)
    action.log = MagicMock()

    action.module.configuration = {
        "domain": "https://test.atlassian.net",
        "email": "john.doe@gmail.com",
        "api_key": "my-client-secret",
    }

    return action


def test_add_comment(action: JIRAAddCommentToIssue):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://test.atlassian.net/rest/api/3/issue/PRJ-1/comment",
            json={},
        )
        args = JiraAddCommentArguments(issue_key="PRJ-1", comment="Hello, world")
        action.run(args)
