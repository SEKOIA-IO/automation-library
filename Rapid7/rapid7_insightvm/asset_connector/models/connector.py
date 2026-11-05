from pydantic import AliasChoices, Field
from sekoia_automation.asset_connector.models.connector import DefaultAssetConnectorConfiguration

from rapid7_insightvm.asset_connector.models.base import Rapid7BaseModel


class Rapid7InsightVMConnectorConfiguration(DefaultAssetConnectorConfiguration):
    page_size: int = Field(default=50, ge=1, le=500)


class Rapid7PageMetadata(Rapid7BaseModel):
    number: int | None = None
    size: int | None = None
    totalPages: int | None = None
    totalResources: int | None = None
    cursor: str | None = None
    effective_time: str | None = Field(default=None, validation_alias=AliasChoices("effective_time", "effectiveTime"))


class Rapid7Link(Rapid7BaseModel):
    href: str | None = None
    rel: str | None = None
