from sekoia_automation.module import Module

from slack_modules.models import SlackAuditLogsModuleConfiguration


class SlackAuditLogsModule(Module):
    configuration: SlackAuditLogsModuleConfiguration
