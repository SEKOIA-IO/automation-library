import datetime

from dateutil.parser import isoparse
from pydantic import Field

from .connector_fastly_waf_base import FastlyWAFBaseConnector, FastlyWAFBasicConnectorConfiguration


class FastlyWAFAuditConnectorConfiguration(FastlyWAFBasicConnectorConfiguration):
    site: str | None = Field(None, description="Site name", pattern=r"^[0-9a-z_.-]+$")


class FastlyWAFAuditConnector(FastlyWAFBaseConnector):
    def get_datetime_from_item(self, item: dict) -> datetime.datetime:
        return isoparse(item["created"])

    configuration: FastlyWAFAuditConnectorConfiguration

    def get_url_for_site(self, site_name: str) -> str:
        return f"{self.base_uri}/api/v0/corps/{self.configuration.corp}/sites/{site_name}/activity"

    def get_url_for_corp(self) -> str:
        return f"{self.base_uri}/api/v0/corps/{self.configuration.corp}/activity"
