"""Shared rules for what a playbook may hand an action.

Every action that takes an indicator refuses a bad one before spending an API
request, and the wording of that refusal is what an analyst reads when a
workflow stops. Keeping the rules in one place is what makes those messages
identical across actions, and stops one of them quietly drifting into accepting
something the others refuse.
"""

import ipaddress
import re
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})
HASH_LENGTHS: dict[int, str] = {32: "MD5", 40: "SHA1", 64: "SHA256"}
HEX = re.compile(r"\A[0-9a-fA-F]+\Z")
_PUBLIC = "PolySwarm's public community"
LABEL = re.compile(r"\A[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\Z")
# Suffixes that the standards reserve for names that only resolve inside a
# network: mDNS (RFC 6762), ICANN's private-use delegation, and RFC 8375's
# home network zone. Conventions like .lan and .corp are deliberately not here,
# because nothing stops them being registered and refusing them would be a guess.
PRIVATE_SUFFIXES: tuple[str, ...] = (".localhost", ".local", ".internal", ".home.arpa")


def invalid_ip_reason(value: str) -> str | None:
    """Why an IP is refused, or None when it is fine to send to a public service.

    A playbook can hand an action anything a previous step produced, including
    a typo or an address from the customer's own network. Internal addressing
    is refused rather than quietly submitted, which some customers would read
    as a leak of their own topology.
    """
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        return f"'{value}' is not a valid IP address"

    description = _non_public(parsed)
    if description:
        return f"'{value}' is a {description} address and will not be sent to {_PUBLIC}"
    return None


def _non_public(parsed: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    """What kind of internal address this is, or None when it is publicly routable."""
    for test, description in (
        (parsed.is_loopback, "loopback"),
        (parsed.is_link_local, "link-local"),
        (parsed.is_private, "private"),
        (parsed.is_reserved, "reserved"),
        (parsed.is_multicast, "multicast"),
        # Shared address space (100.64.0.0/10) is neither private nor reserved
        # to the stdlib, but it is carrier-internal and routes nowhere public.
        (not parsed.is_global, "non-public"),
    ):
        if test:
            return description

    return None


def invalid_url_reason(value: str) -> str | None:
    """Why a URL is refused, or None when it is safe to send to a public service.

    The module never fetches the URL, but a community is shared: whatever is
    submitted is visible to every engine in it and cannot be taken back. A URL
    on an internal host therefore publishes the customer's network layout just
    as an internal IP would, so the host is held to the same rule as an IP
    action. Single-label names such as http://fileserver/ are refused as well:
    they only resolve inside a network, and no public URL looks like that.
    """
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        return f"'{_without_credentials(value)}' is not a valid URL"

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        return f"'{_without_credentials(value)}' does not use the http or https scheme"

    # Report the host, not the URL, wherever there is one: a URL can carry a
    # username and password, and a refusal is written to the playbook log.
    if not host:
        return f"'{_without_credentials(value)}' has no host"
    host = host.rstrip(".").lower()

    try:
        ipaddress.ip_address(host)
    except ValueError:
        # Forms like 127.1, 2130706433 or 0x7f.0.0.1 are not literals to the
        # ipaddress module but connect to the address they spell.
        try:
            socket.inet_aton(host)
        except OSError:
            pass
        else:
            return f"The host '{host}' is an IP address written in an unusual form and will not be sent to {_PUBLIC}"
    else:
        description = _non_public(ipaddress.ip_address(host))
        if description:
            return f"The URL points at a {description} address '{host}' and will not be sent to {_PUBLIC}"
        return None

    if host == "localhost" or host.endswith(PRIVATE_SUFFIXES) or "." not in host:
        return f"The host '{host}' only exists inside a network and will not be sent to {_PUBLIC}"

    return None


def _without_credentials(value: str) -> str:
    """A URL with any username and password taken out, safe to put in a message."""
    marker = value.rfind("@")
    if marker == -1:
        return value
    scheme_end = value.find("//")
    if scheme_end == -1 or marker < scheme_end:
        return value
    return f"{value[: scheme_end + 2]}{value[marker + 1 :]}"


def invalid_domain_reason(value: str, ip_action: str = "ScanIp") -> str | None:
    """Why a domain is refused, or None when it is a plausible hostname.

    An IP is refused with a pointer to the action that handles one, because
    passing an address to a domain action is a mistake worth naming rather than
    a failure worth inheriting. The caller names that action, since a search and
    a scan want the analyst sent to different places.
    """
    candidate = value.strip().rstrip(".")
    if not candidate:
        return f"'{value}' is not a plausible hostname"

    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        pass
    else:
        return f"'{value}' is an IP address, not a domain. Use the {ip_action} action for an address"

    if len(candidate) > 253 or "." not in candidate:
        return f"'{value}' is not a plausible hostname"
    if not all(LABEL.match(label) for label in candidate.split(".")):
        return f"'{value}' is not a plausible hostname"

    return None


def invalid_hash_reason(value: str) -> str | None:
    """Why a hash is refused, or None when it could be an MD5, SHA1 or SHA256.

    The platform would reject a malformed hash anyway, but only after the
    request has been spent, and a bulk lookup can spend one per hash.
    """
    candidate = value.strip()
    if not candidate:
        return "no hash was supplied"
    if len(candidate) not in HASH_LENGTHS or not HEX.match(candidate):
        return f"'{value}' is not a plausible MD5, SHA1 or SHA256 hash: expected 32, 40 or 64 hexadecimal characters"
    return None


def hash_kind(value: str) -> str | None:
    """The hash algorithm a value could be, or None when it is not a hash."""
    return HASH_LENGTHS.get(len(value.strip())) if HEX.match(value.strip() or " ") else None
