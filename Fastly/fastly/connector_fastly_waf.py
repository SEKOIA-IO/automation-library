import datetime

from dateutil.parser import isoparse
from pydantic import Field

from .connector_fastly_base import FastlyBasicConnectorConfiguration, FastlyConnectorBase


class FastlyWAFConnectorConfiguration(FastlyBasicConnectorConfiguration):
    email: str = Field(..., description="User's email")
    token: str = Field(..., description="API token")
    corp: str = Field(..., description="Corporation name", pattern=r"^[0-9a-z_.-]+$")
    site: str = Field(..., description="Site name", pattern=r"^[0-9a-z_.-]+$")

    frequency: int = 60
    chunk_size: int = 1000


class FastlyWAFConnector(FastlyConnectorBase):
    configuration: FastlyWAFConnectorConfiguration

    def get_next_url(self, from_datetime: datetime.datetime) -> str:
        from_timestamp = int(from_datetime.timestamp())
        next_url = (
            f"{self.base_uri}/api/v0/corps/{self.configuration.corp}/sites/{self.configuration.site}/events?"
            f"sort=asc&limit={self.configuration.chunk_size}&from={from_timestamp}"
        )
        return next_url
