import re
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
