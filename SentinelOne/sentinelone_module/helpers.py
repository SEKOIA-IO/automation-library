import re
import secrets
import string
from datetime import UTC, datetime
from typing import Callable, Sequence

import six
from cachetools import Cache
from stix2patterns.pattern import Pattern


def camelize(string: str) -> str:
    return re.sub(r"_(.)", lambda m: m.group(1).upper(), string)


RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def to_rfc3339(date: datetime):
    """
    Return the datetime as RFC3339 strict format
    """
    assert date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None
    return date.astimezone(UTC).strftime(RFC3339_STRICT_FORMAT)


def generate_password(length: int = 64) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation

    while True:
        candidate = "".join(secrets.choice(alphabet) for i in range(max(10, length)))
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c.isdigit() for c in candidate)
            and any(True if c in string.punctuation else False for c in candidate)
        ):
            return candidate


def is_a_supported_stix_indicator(stix_object):
    # Check if object is an indicator
    if stix_object.get("type") != "indicator":
        return False

    # Check if indicator is STIX
    pattern_type = stix_object.get("pattern_type")
    if pattern_type is not None and pattern_type != "stix":
        return False
    else:
        return True


def stix_to_indicators(stix_object, supported_types_map):

    if not is_a_supported_stix_indicator(stix_object):
        return []

    parsed_pattern = Pattern(stix_object["pattern"])
    results = []
    for observable_type, comparisons in six.iteritems(parsed_pattern.inspect().comparisons):
        if observable_type not in supported_types_map:
            continue

        for path, operator, value in comparisons:
            try:
                path = ".".join(path)
            except TypeError:
                # This happens when the pattern contains '*', which is unsupported
                continue

            if path not in supported_types_map[observable_type]:
                continue

            if operator != "=":
                continue
            # Get ioc type and value
            ioc_type = supported_types_map[observable_type][path]
            ioc_value = value.strip("'")

            results.append({"type": ioc_type, "value": ioc_value})

    return results


def filter_collected_events(events: Sequence, getter: Callable, cache: Cache) -> list:
    """
    Filter events that have already been filter_collected_events

    Args:
        events: The list of events to filter
        getter: The callable to get the criteria to filter the events
        cache: The cache that hold the list of collected events
    """

    selected_events = []
    for event in events:
        key = getter(event)

        # If the event was already collected, discard it
        if key is None or key in cache:
            continue

        cache[key] = True
        selected_events.append(event)

    return selected_events
