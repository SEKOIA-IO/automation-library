from sekoia_automation.module import Module

from jira_modules.action_change_issue_status import JIRAChangeIssueStatus
from jira_modules.action_comment_issue import JIRAAddCommentToIssue
from jira_modules.action_create_issue import JIRACreateIssue

if __name__ == "__main__":
    module = Module()

    module.register(JIRACreateIssue, "jira_create_issue")
    module.register(JIRAAddCommentToIssue, "jira_add_comment")
    module.register(JIRAChangeIssueStatus, "jira_change_status")

    module.run()
