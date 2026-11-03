"""Helpers shared by the flow logs connectors."""

import ipaddress
from collections.abc import Iterable
from typing import Any


def check_all_ips_are_private(candidates: Iterable[Any]) -> bool:
    """
    Check if all the IPs found in the candidates are private.

    Candidates that are not valid IP addresses are ignored.

    Args:
        candidates: values that may be IP addresses

    Returns:
        bool: True if every valid IP is private (or if there is none)
    """
    for candidate in candidates:
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue

        if not ip.is_private:
            return False

    return True


def filter_internal_traffic(filter: bool, candidates: Iterable[Any]) -> bool:
    """
    Filter internal traffic based on the configuration.

    Args:
        filter: whether to filter internal traffic
        candidates: values that may be IP addresses

    Returns:
        bool: True if the record should be filtered out
    """
    return filter and check_all_ips_are_private(candidates)
