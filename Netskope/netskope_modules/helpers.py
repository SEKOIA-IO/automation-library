import hashlib
from urllib.parse import urlparse

from netskope_modules.types import NetskopeAlertType, NetskopeEventType


def get_iterator_name(event_type: NetskopeEventType, alert_type: NetskopeAlertType | None) -> str:
    """
    return a name for an iterator

    :param NetskopeEventType event_type: the type of the event
    :param NetskopeAlertType or None alert_type: the type of alert
    :rtype: str
    :return: The name for the iterator
    """
    parts = [event_type.value]

    if alert_type is not None:
        parts.append(alert_type.value)

    return "-".join(parts)


def get_index_name(prefix: str, event_type: NetskopeEventType, alert_type: NetskopeAlertType | None) -> str:
    """
    return a index name for the iterator

    :param NetskopeEventType event_type: the type of the event
    :param NetskopeAlertType or None alert_type: the type of alert
    """
    # otherwise, create it
    hash_sum = hashlib.sha256()
    hash_sum.update(prefix.encode("utf-8"))
    hash_sum.update(event_type.value.encode("utf-8"))

    if event_type == "alert" and alert_type is not None:
        hash_sum.update(alert_type.value.encode("utf-8"))

    return f"sekoiaio-consumer-{hash_sum.hexdigest()}"


def get_tenant_hostname(location: str) -> str:
    """
    Return the hostname of the tenant from the location

    :param str location: The location of the tenant
    :rtype: str
    :return: The hostname of the tenant
    """
    # if the location is already a hostname
    if not location.strip().startswith("http"):
        return location

    # otherwise, parse the url
    url = urlparse(location)

    # and return the netloc
    return url.netloc
