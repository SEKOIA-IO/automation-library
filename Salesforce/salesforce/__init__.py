"""Module ad connector for Salesforce."""

from sekoia_automation.module import Module

from salesforce.models import SalesforceModuleConfig


class SalesforceModule(Module):
    """SalesforceModule."""

    configuration: SalesforceModuleConfig
