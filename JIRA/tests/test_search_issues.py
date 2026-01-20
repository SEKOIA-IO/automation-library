from unittest.mock import MagicMock

import pytest
import requests_mock

from jira_modules.action_search_issues import JIRASearchIssues, JIRASearchIssuesArguments
from jira_modules.base import JIRAModule


@pytest.fixture
def action():
    module = JIRAModule()

    action = JIRASearchIssues(module)
    action.log = MagicMock()

    action.module.configuration = {
        "domain": "https://test.atlassian.net",
        "email": "john.doe@gmail.com",
        "api_key": "my-client-secret",
    }

    return action


def test_search_issues(action: JIRASearchIssues):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://test.atlassian.net/rest/api/3/search/jql",
            json={"issues": [{"id": "10000"}, {"id": "10001"}, {"id": "10002"}]},
        )
        args = JIRASearchIssuesArguments()
        action.run(args)
