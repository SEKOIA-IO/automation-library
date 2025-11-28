from sekoia_automation.module import Module
from workday.client import WorkdayClientConfiguration


class WorkdayModule(Module):
    """Workday module for Sekoia.io automation"""

    configuration: WorkdayClientConfiguration
