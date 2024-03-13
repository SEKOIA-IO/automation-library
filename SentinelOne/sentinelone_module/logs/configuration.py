from uuid import UUID

from sekoia_automation.connector import DefaultConnectorConfiguration


class SentinelOneLogsConnectorConfiguration(DefaultConnectorConfiguration):
    uuid: UUID
    last_activity_created_at: str | None = None
    last_threat_created_at: str | None = None
