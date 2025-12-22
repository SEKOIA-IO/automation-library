from jira_modules.action_change_issue_status import JIRAChangeIssueStatus
from jira_modules.action_comment_issue import JIRAAddCommentToIssue
from jira_modules.action_create_issue import JIRACreateIssue
from jira_modules.action_get_issue import JIRAGetIssue
from jira_modules.action_search_issues import JIRASearchIssues
from jira_modules.base import JIRAModule

if __name__ == "__main__":
    module = JIRAModule()

    module.register(JIRACreateIssue, "jira_create_issue")
    module.register(JIRAAddCommentToIssue, "jira_add_comment")
    module.register(JIRAChangeIssueStatus, "jira_change_status")
    module.register(JIRASearchIssues, "jira_search_issues")
    module.register(JIRAGetIssue, "jira_get_issue")

    module.run()
