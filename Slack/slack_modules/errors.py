class SlackAuditLogsError(Exception):
    """Any failure while talking to the Slack Audit Logs API."""


class AuthenticationError(SlackAuditLogsError):
    """The token is missing, revoked, expired, or lacks auditlogs:read."""


class PlanError(SlackAuditLogsError):
    """The Slack organization is not on a plan exposing the Audit Logs API."""
