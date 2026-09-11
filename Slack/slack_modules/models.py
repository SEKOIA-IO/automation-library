from pydantic import BaseModel, Field


class SlackAuditLogsModuleConfiguration(BaseModel):
    token: str = Field(
        description=(
            "Slack user token (xoxp-…) carrying the auditlogs:read scope, issued by "
            "installing the app on the Enterprise organization as its Owner"
        ),
        json_schema_extra={"secret": True},
    )
    base_url: str = Field(
        default="https://api.slack.com/audit/v1",
        description="Base URL of the Slack Audit Logs API",
    )
