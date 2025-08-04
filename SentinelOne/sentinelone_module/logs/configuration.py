from sekoia_automation.connector import DefaultConnectorConfiguration


class SentinelOneLogsConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    activities_batch_size: int = 1000
    threats_batch_size: int = 1000
