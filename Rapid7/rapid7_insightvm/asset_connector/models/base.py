from typing import Annotated, Any, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator
from pydantic.fields import FieldInfo


def _coerce_id(value: Any) -> Any:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return value


def _coerce_reference(value: Any) -> Any:
    if isinstance(value, dict):
        value = value.get("id")
    return _coerce_id(value)


StrId = Annotated[str, BeforeValidator(_coerce_id)]
Reference = Annotated[str, BeforeValidator(_coerce_reference)]


class Rapid7BaseModel(BaseModel):

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _null_to_default(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        fields = cast(dict[str, FieldInfo], cls.model_fields)

        return {
            key: value
            for key, value in data.items()
            if value is not None or key not in fields or fields[key].is_required()
        }
