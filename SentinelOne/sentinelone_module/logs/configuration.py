from sekoia_automation.connector import DefaultConnectorConfiguration


class SentinelOneLogsConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
