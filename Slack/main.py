from slack_modules import SlackAuditLogsModule
from slack_modules.connector import SlackAuditLogsConnector
from slack_modules.validator import SlackAuditLogsAccountValidator

if __name__ == "__main__":
    module = SlackAuditLogsModule()
    module.register(SlackAuditLogsConnector, "SlackAuditLogsConnector")
    module.register_account_validator(SlackAuditLogsAccountValidator)
    module.run()
