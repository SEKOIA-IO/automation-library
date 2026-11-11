"""Checks run on playbook input before any request is spent on urlscan.io."""

import ipaddress
import re
import socket
import unicodedata
from typing import Any
from urllib.parse import urlsplit

from urlscan_modules.base import ActionError

SUFFIX = "and will not be sent to urlscan.io"
SCAN_ID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
# Suffixes the standards reserve for names that only resolve inside a network.
INTERNAL_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")
NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")


def internal_target_reason(url: str) -> str | None:
    """Why a URL must not be submitted to urlscan.io, or None when it may be.

    urlscan.io publishes what it scans, so a URL on an internal host would leak the customer's network layout.
    No DNS lookup is made: only the host as written is checked.
    """
    value = url.strip()
    if "://" not in value:
        value = "http://" + value.lstrip("/")

    try:
        parts = urlsplit(value)
        hostname = parts.hostname
    except ValueError:
        return f"The URL has no valid host {SUFFIX}"

    if "\\" in parts.netloc:
        return f"The URL has a backslash in its host part, which parsers read differently, {SUFFIX}"

    host = unicodedata.normalize("NFKC", hostname or "").lower().rstrip(".")
    if not host:
        return f"The URL has no valid host {SUFFIX}"

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        for candidate in _addresses_to_check(address):
            if not candidate.is_global:
                return f"The URL host '{host}' is a {_kind(candidate)} address {SUFFIX}"
        return None

    # The checks below are written against the host as urlsplit reads it, so a host
    # that a browser style parser would decode differently is refused outright.
    if "%" in host:
        return f"The URL host '{host}' is percent-encoded, which parsers read differently, {SUFFIX}"

    # Forms like 127.1, 2130706433 or 0x7f.0.0.1 are not literals to ipaddress but connect to the address they spell.
    try:
        socket.inet_aton(host)
    except OSError, ValueError:
        pass
    else:
        return f"The URL host '{host}' is an IP address written in an unusual form {SUFFIX}"

    if host == "localhost" or "." not in host or host.endswith(INTERNAL_SUFFIXES):
        return f"The URL host '{host}' only exists inside a network {SUFFIX}"

    return None


def _addresses_to_check(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """The address itself, then the IPv4 address an IPv6 one carries, if any."""
    addresses = [address]
    if isinstance(address, ipaddress.IPv6Address):
        embedded: list[ipaddress.IPv4Address | None] = [address.ipv4_mapped, address.sixtofour]
        embedded.append(address.teredo[1] if address.teredo else None)
        if address in NAT64_PREFIX:
            embedded.append(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF))
        if int(address) < 2**32 and address not in (ipaddress.IPv6Address("::"), ipaddress.IPv6Address("::1")):
            embedded.append(ipaddress.IPv4Address(int(address)))
        addresses.extend(item for item in embedded if item is not None)
    return addresses


def _kind(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    for is_kind, kind in (
        (address.is_loopback, "loopback"),
        (address.is_link_local, "link-local"),
        (address.is_private, "private"),
        (address.is_reserved, "reserved"),
        (address.is_multicast, "multicast"),
    ):
        if is_kind:
            return kind
    return "non-public"


def valid_scan_id(value: Any) -> str:
    """The scan UUID in lower case, or an ActionError when the value is not one."""
    scan_id = str(value).strip().lower()
    if not SCAN_ID_PATTERN.match(scan_id):
        raise ActionError(f"'{value}' is not a valid scan UUID")
    return scan_id
