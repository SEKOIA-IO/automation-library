from collections import defaultdict, namedtuple
from collections.abc import Generator, Iterator

import six
from stix2patterns.pattern import Pattern

from crowdstrike_falcon.constants import VERTICLES_TYPE_MAPPING


class VerticleID(namedtuple("VerticleId", ["type", "device_id", "object_id"])):
    @classmethod
    def parse(cls, verticle_id_str: str) -> "VerticleID":
        """
        Parse the verticle id
        """
        parts = verticle_id_str.split(":")

        if len(parts) != 3:
            raise ValueError(f"Invalid verticle id: {verticle_id_str}")

        return cls._make(parts)


def get_extended_verticle_type(verticle_id_str: str | None) -> str | None:
    """
    Return the extended verticle type

    :param str verticle_id_str: The string representation of the verticle type
    :return: The extendted verticle type if matching, None otherwise
    :rtype: str | None
    """
    if verticle_id_str is None:
        return None

    verticle_id = VerticleID.parse(verticle_id_str)
    return VERTICLES_TYPE_MAPPING.get(verticle_id.type)


def group_edges_by_verticle_type(edges: Iterator, chunk_size: int = 100) -> Generator[tuple[str, list], None, None]:
    """
    Group edges by the type of the pointed verticle

    :param Sequence edges: The list of edges
    :param int chunk_size: The size of chunks
    :return: A list of egde, with their type of their pointed verticle, as generator
    :rtype: generator
    """
    chunks: dict[str, list] = defaultdict(list)

    for edge in edges:
        # get the verticle id pointed by the edge
        verticle_id = edge.get("id")
        if verticle_id is None:
            continue

        # get the extended type of the verticle from its id
        try:
            verticle_type = get_extended_verticle_type(verticle_id)
        except ValueError:
            verticle_type = None

        if verticle_type is None:
            continue

        # add the edge to the chunk dedicated to the verticle type
        chunks[verticle_type].append(edge)

        # check if the chunk for the verticle type is full
        if len(chunks[verticle_type]) >= chunk_size:
            yield (verticle_type, chunks[verticle_type])
            chunks[verticle_type] = []

    # yield remaining non-empty chunks
    for verticle_type, chunk in chunks.items():
        if len(chunk) > 0:
            yield (verticle_type, chunk)


def get_detection_id(event: dict) -> str | None:
    """
    For detection summary event, return the identifier of the detection.
    Otherwise, return None

    :param dict event: The event
    :return: identifier of the detection if the event is a detection summary event, None otherwise
    :rtype: str | None
    """
    # Is a detection summary event?
    event_type = event.get("metadata", {}).get("eventType")
    if event_type != "DetectionSummaryEvent":
        return None

    return event.get("event", {}).get("DetectId")


def get_epp_detection_composite_id(event: dict) -> str | None:
    """
    For EPP detection summary event, return the identifier of the detection.
    Otherwise, return None

    :param dict event: The event
    :return: identifier of the detection if the event is a detection summary event, None otherwise
    :rtype: str | None
    """
    # Is a epp detection summary event?
    event_type = event.get("metadata", {}).get("eventType")
    if event_type != "EppDetectionSummaryEvent":
        return None

    return event.get("event", {}).get("CompositeId")


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
    """
    Extract indicators type and value from the STIX pattern.

    supported_types_map is used to define the mapping from STIX pattern
    to the different IOCs types supported by Crowdstrike Falcon.
    "stix_root_key": {"stix_sub_key": "target_type"}
    Example with ipv4:
    Mapping with "ipv4-addr": {"value": "ipv4"} for IOC "[ipv4-addr:value = 'X.X.X.X']"
    """
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


def compute_refresh_interval(interval: int) -> int:
    """
    Compute a refresh interval with a safety margin

    This margin is depends on the refresh interval and a maximum of five minutes.
    The refresh interval is a minimum of 30 seconds
    """
    delta = min(300, int(interval / 6))
    return max(30, interval - delta)
