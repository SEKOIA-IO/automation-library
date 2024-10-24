import six
from stix2patterns.pattern import Pattern


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
