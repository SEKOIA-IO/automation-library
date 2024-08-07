from datetime import datetime

from management.mgmtsdk_v2.entities.activity import Activity
from management.mgmtsdk_v2.entities.threat import Threat


def get_latest_event_timestamp(events: list[Activity | Threat | dict]) -> datetime | None:
    """Searches for the most recent timestamp from a list of events

    Args:
        events (list[Activity | Threat | dict]): List of events to

    Returns:
        datetime: Timestamp of the most recent event of the list
    """
    latest_event_datetime: datetime | None = None
    for event in events:
        event_dict = event if isinstance(event, dict) else event.__dict__
        if event_dict.get("createdAt") is not None:
            if latest_event_datetime is None:
                latest_event_datetime = datetime.fromisoformat(event_dict["createdAt"])
            else:
                event_created_at = datetime.fromisoformat(event_dict["createdAt"])
                if event_created_at > latest_event_datetime:
                    latest_event_datetime = event_created_at

    return latest_event_datetime
