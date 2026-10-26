from typing import Any, cast

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.fields import FieldInfo


class TenableBaseModel(BaseModel):
    """Base model tolerating the explicit ``null`` values of the Tenable API.

    Tenable may report a field it has no value for as ``null`` instead of omitting it, and a pydantic default
    only applies to an absent key: a single ``"see_also": null`` or ``"ipv4s": null`` would fail the validation
    of the whole record.

    Those nulls are dropped so the declared default applies. Nulls on required fields are kept so a genuinely
    malformed record still fails.
    """

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _null_to_default(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # `cls.model_fields` is typed as an instance property, hence the cast.
        fields = cast(dict[str, FieldInfo], cls.model_fields)

        return {
            key: value
            for key, value in data.items()
            if value is not None or key not in fields or fields[key].is_required()
        }
