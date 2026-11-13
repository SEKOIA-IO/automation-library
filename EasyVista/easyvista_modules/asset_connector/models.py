from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator

# EasyVista fills absent values with empty strings or a dash
EMPTY_VALUES = {"", "-"}


def _parse_date(value: Any) -> Any:
    # ponytail: ISO 8601 only (format of the API examples). Dates follow the locale of the API user:
    # another format is dropped, request `formatDate` if such tenants show up.
    if not isinstance(value, str):
        return value
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


Date = Annotated[datetime | None, BeforeValidator(_parse_date)]


class EasyVistaModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _empty_to_none(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        return {
            key: None if isinstance(value, str) and value.strip() in EMPTY_VALUES else value
            for key, value in data.items()
        }


class EasyVistaLocation(EasyVistaModel):
    CITY: str | None = None


class EasyVistaEmployee(EasyVistaModel):
    E_MAIL: str | None = None


class EasyVistaCatalogAsset(EasyVistaModel):
    ARTICLE_MODEL: str | None = None
    SMBIOS_NAME: str | None = None


class EasyVistaAsset(EasyVistaModel):
    """Record of GET /assets (table AM_ASSET). Every value is a string."""

    ASSET_ID: str
    ASSET_LABEL: str | None = None
    ASSET_TAG: str | None = None
    SERIAL_NUMBER: str | None = None
    NETWORK_IDENTIFIER: str | None = None
    SERVER_TYPE_ID: str | None = None
    DEPARTMENT_ID: str | None = None
    DEPARTMENT_PATH: str | None = None
    ENTRY_DATE: Date = None
    INSTALLATION_DATE: Date = None
    LAST_UPDATE: Date = None
    LAST_AUTOMATIC_DISCOVERY: Date = None
    # Kept raw: a removal date must exclude the asset whatever its format
    REMOVED_DATE: str | None = None
    RECYCLED_DATE: str | None = None
    LOCATION: EasyVistaLocation | None = None
    EMPLOYEE: EasyVistaEmployee | None = None
    CATALOG_ASSET: EasyVistaCatalogAsset | None = None

    @property
    def is_removed(self) -> bool:
        return self.REMOVED_DATE is not None or self.RECYCLED_DATE is not None
