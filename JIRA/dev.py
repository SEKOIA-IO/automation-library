"""
This script is for a local debug only
"""

import argparse
import logging
from pathlib import Path

from jira_modules.action_change_issue_status import JIRAChangeIssueStatus, JiraChangeStatusArguments
from jira_modules.action_comment_issue import JiraAddCommentArguments, JIRAAddCommentToIssue
from jira_modules.action_create_issue import JIRACreateIssue, JiraCreateIssueArguments
from jira_modules.base import JIRAConfiguration, JIRAModule

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s", datefmt="%d-%b-%y %H:%M:%S"
)
logger = logging.getLogger(__name__)


def dumb_log(message: str, level: str, **kwargs):
    log_level = logging.getLevelName(level.upper())
    logger.log(log_level, message)


def dumb_log_exception(exception: Exception, **kwargs):
    message = kwargs.get("message", "An exception occurred")
    logger.exception(message, exc_info=exception)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", type=str, required=True)
    parser.add_argument("--email", type=str, required=True)
    parser.add_argument("--api_key", type=str, required=True)

    args = parser.parse_args()

    module_conf = JIRAConfiguration(domain=args.domain, email=args.email, api_key=args.api_key)

    module = JIRAModule()
    module.configuration = module_conf

    # args = JiraCreateIssueArguments(
    #    project_key="<PROJECT_KEY>",
    #    summary="Another Task",
    #    issue_type="Task",
    #    due_date="2077-10-23",
    #    labels="dev,cloud9",
    #    assignee=None,
    #    reporter=None,
    #    priority="High",
    #    parent_key=None,
    # )
    # action = JIRACreateIssue(module=module, data_path=Path("."))
    # action.log = dumb_log
    # action.log_exception = dumb_log_exception
    # action.run(args)

    # args = JiraAddCommentArguments(
    #    issue_key=<ISSUE_KEY>,
    #    comment="Some comment"
    # )
    # action = JIRAAddCommentToIssue(module=module, data_path=Path("."))
    # action.log = dumb_log
    # action.log_exception = dumb_log_exception
    # action.run(args)

    # args = JiraChangeStatusArguments(issue_key=<ISSUE_KEY>, status_name="Done")
    # action = JIRAChangeIssueStatus(module=module, data_path=Path("."))
    # action.log = dumb_log
    # action.log_exception = dumb_log_exception
    # action.run(args)
