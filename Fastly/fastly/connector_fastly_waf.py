import datetime

from dateutil.parser import isoparse
from pydantic import Field

from .connector_fastly_waf_base import FastlyWAFBaseConnector, FastlyWAFBasicConnectorConfiguration


class FastlyWAFConnectorConfiguration(FastlyWAFBasicConnectorConfiguration):
    email: str = Field(..., description="User's email")
    token: str = Field(..., description="API token")
    corp: str = Field(..., description="Corporation name", pattern=r"^[0-9a-z_.-]+$")
    site: str = Field(..., description="Site name", pattern=r"^[0-9a-z_.-]+$")

    frequency: int = 60
    chunk_size: int = 1000


class FastlyWAFConnector(FastlyWAFBaseConnector):
    configuration: FastlyWAFConnectorConfiguration

    def get_url_for_site(self, site_name: str) -> str:
        return f"{self.base_uri}/api/v0/corps/{self.configuration.corp}/sites/{self.configuration.site}/events"

    def get_url_for_corp(self) -> str | None:
        return None

    def get_datetime_from_item(self, item: dict) -> datetime.datetime:
        return isoparse(item["timestamp"])
