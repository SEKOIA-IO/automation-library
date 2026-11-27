import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

MAPPING = {
    "device_event_class_id": "type",
    "name": "name",
    "severity": "severity",
    "source": "suser",
    "when": "end",
    "user_id": "duid",
    "created_at": "rt",
    "full_file_path": "filePath",
    "location": "dhost",
}


def translate_fields(data: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(data.items()):
        if key in MAPPING:
            del data[key]
            data[MAPPING[key]] = value

    return data


def strip_null_values(data: dict[str, Any]) -> dict[str, Any]:
    for k in list(data.keys()):
        if data[k] is None:
            del data[k]

    return data


def parse_iso8601_timestamp(raw: Any) -> float | None:
    """Parse an ISO 8601 date (with or without fractional seconds or offset) into a POSIX timestamp."""
    if not isinstance(raw, str):
        return None

    value = raw.strip()
    if not value:
        return None

    if value[-1] in "Zz":
        value = f"{value[:-1]}+00:00"

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def latest_timestamp(items: Iterable[dict[str, Any]], keys: Iterable[str]) -> float | None:
    """Return the most recent timestamp of the items, using the first parseable key of each item."""
    keys = tuple(keys)
    most_recent: float | None = None
    for item in items:
        for key in keys:
            parsed = parse_iso8601_timestamp(item.get(key))
            if parsed is not None:
                if most_recent is None or parsed > most_recent:
                    most_recent = parsed
                break
    return most_recent


THREAT_REGEX = re.compile("'(?P<detection_identity_name>.*?)'.+'(?P<filePath>.*?)'")
DLP_REGEX = re.compile(
    "An \u2033(?P<name>.+)\u2033.+ Username: (?P<user>.+?) {2}"
    "Rule names: \u2032(?P<rule>.+?)\u2032 {2}"
    "User action: (?P<user_action>.+?) {2}Application Name: (?P<app_name>.+?) {2}"
    "Data Control action: (?P<action>.+?) {2}"
    "File type: (?P<file_type>.+?) {2}File size: (?P<file_size>\\d+?) {2}"
    "Source path: (?P<file_path>.+)$"
)
REGEX_MAPS = {
    "Event::Endpoint::Threat::*": THREAT_REGEX,
    "Event::Endpoint::DataLossPreventionUserAllowed": DLP_REGEX,
}


def extract_info(data: dict[str, Any]) -> dict[str, Any]:
    if "description" in data.keys():
        data["name"] = data["description"]

    if data.get("type"):
        regex = None
        for type, type_regex in REGEX_MAPS.items():
            if (type[-1] == "*" and data["type"].startswith(type[:-1])) or (type == data["type"]):
                regex = type_regex

        if regex:
            match = regex.search(data["name"])
            if match:
                data.update(match.groupdict())
                if "detection_identity_name" in data:
                    data["name"] = data["detection_identity_name"]

    return data


def normalize_message(data: dict[str, Any]) -> dict[str, Any]:
    return extract_info(translate_fields(strip_null_values(data)))
