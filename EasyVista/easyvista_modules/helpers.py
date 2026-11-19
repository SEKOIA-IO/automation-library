from pydantic import BaseModel

from easyvista_modules.action_base import EasyVistaAction


def map_fields(model: BaseModel, mapping: dict[str, str]) -> dict:
    """Ignore empty playbook text defaults; keep custom values verbatim, including blanks."""
    values = model.model_dump(exclude_none=True)
    explicit = {api_name: values[name] for name, api_name in mapping.items() if name in values and values[name] != ""}
    explicit_names = {name.casefold() for name in explicit}
    custom = {
        key: value
        for key, value in (values.get("custom_fields") or {}).items()
        if key.casefold() not in explicit_names and value is not None
    }
    return {**custom, **explicit}


def select_fields(data: dict | None, mapping: dict[str, str]) -> dict | None:
    if data is None:
        return None
    return {name: data[api_name] for name, api_name in mapping.items() if api_name in data}


LIST_FIELDS = {
    "href": "HREF",
    "record_count": "record_count",
    "total_record_count": "total_record_count",
    "records": "records",
}

QUESTIONNAIRE_FIELDS = {
    "href": "HREF",
    "record_count": "record_count",
    "total_record_count": "total_record_count",
    "results": "results",
}


def validate_identifiers(action: EasyVistaAction, values: dict, type_fields: tuple[str, ...]) -> bool:
    if not any((values.get(name) for name in type_fields)):
        action.error("Provide one of " + (", ".join(type_fields[:-1]) + " or " + type_fields[-1]))
        return False
    if not any((values.get(name) for name in ("group_id", "group_name", "group_mail"))):
        action.error("Provide one of group_id, group_name or group_mail")
        return False
    return True
