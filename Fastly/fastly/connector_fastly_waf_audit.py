import datetime

from dateutil.parser import isoparse
from pydantic import Field

from .connector_fastly_base import FastlyBasicConnectorConfiguration, FastlyConnectorBase


class FastlyWAFAuditConnectorConfiguration(FastlyBasicConnectorConfiguration):
    site: str | None = Field(None, description="Site name", pattern=r"^[0-9a-z_.-]+$")


class FastlyWAFAuditConnector(FastlyConnectorBase):
    configuration: FastlyWAFAuditConnectorConfiguration

    def get_datetime_from_item(self, item: dict) -> datetime.datetime:
        return isoparse(item["created"])

    def get_next_url(self, from_datetime: datetime.datetime) -> str:
        from_timestamp = int(from_datetime.timestamp())

        if self.configuration.site:
            return (
                f"{self.base_uri}/api/v0/corps/{self.configuration.corp}/sites/{self.configuration.site}/activity?"
                f"sort=asc&limit={self.configuration.chunk_size}&from={from_timestamp}"
            )

        else:
            return (
                f"{self.base_uri}/api/v0/corps/{self.configuration.corp}/activity?"
                f"sort=asc&limit={self.configuration.chunk_size}&from={from_timestamp}"
            )
