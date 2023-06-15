import uuid
from datetime import datetime, timedelta, timezone

import orjson
from dateutil.parser import parse

RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def format_datetime(date: datetime) -> str:
    return date.astimezone(timezone.utc).strftime(RFC3339_STRICT_FORMAT)


def normalize_since_time(initial_since_time: str | None) -> datetime:
    now = datetime.now(timezone.utc)

    # if the initial since time is undefined, return now
    if initial_since_time is None:
        return now

    # parse the date
    date = parse(initial_since_time)

    # check if the date is older than the 30 days ago
    thirsty_days_ago = now - timedelta(days=30)
    if date < thirsty_days_ago:
        date = thirsty_days_ago

    return date.astimezone(timezone.utc)


def split_message(message: dict) -> list:
    result = []

    def add(event: dict):
        result.append(orjson.dumps(event).decode("utf-8"))

    for part in message.pop("msgParts", []):
        part_uuid = uuid.uuid4()

        for url in part.pop("urls", []):
            add(
                {
                    "guid": message["guid"],
                    "ts": message["ts"],
                    "type": "msgPartsUrl",
                    "part_uuid": part_uuid,
                    "url": url.get("url"),
                    "src": url.get("src", []),
                    "disposition": message.get("filter", {}).get("disposition"),
                }
            )

        add(
            {
                "msgParts": part,
                "guid": message["guid"],
                "type": "msgParts",
                "ts": message["ts"],
                "uuid": part_uuid,
                "disposition": message.get("filter", {}).get("disposition"),
            }
        )

    add(message)
    return result
