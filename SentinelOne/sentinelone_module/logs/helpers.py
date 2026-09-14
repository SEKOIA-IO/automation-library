from datetime import datetime

from management.mgmtsdk_v2.entities.activity import Activity
from management.mgmtsdk_v2_1.entities.threat import Threat


def _get_event_created_at(event_dict: dict) -> str | None:
    """Returns the ``createdAt`` value of an event.

    In the SentinelOne v2.1 threats API the ``createdAt`` field is nested under
    ``threatInfo``, which the library exposes as an object, so we read it from
    either a dict or an entity.
    """
    created_at = event_dict.get("createdAt")
    if created_at is None:
        threat_info = event_dict.get("threatInfo")
        if isinstance(threat_info, dict):
            created_at = threat_info.get("createdAt")
        elif threat_info is not None:
            created_at = getattr(threat_info, "createdAt", None)

    return created_at


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
        created_at = _get_event_created_at(event_dict)
        if created_at is not None:
            event_created_at = datetime.fromisoformat(created_at)
            if latest_event_datetime is None or event_created_at > latest_event_datetime:
                latest_event_datetime = event_created_at

    return latest_event_datetime
