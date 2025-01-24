from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration


class WizIssuesConnectorConfig(DefaultConnectorConfiguration):
    """WizIssuesConnector configuration."""


class WizIssuesConnector(AsyncConnector):
    """WizIssuesConnector."""
    configuration: WizIssuesConnectorConfig
