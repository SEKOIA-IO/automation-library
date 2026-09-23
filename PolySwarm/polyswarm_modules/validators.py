"""Shared rules for what a playbook may hand an action.

Every action that takes an indicator refuses a bad one before spending an API
request, and the wording of that refusal is what an analyst reads when a
workflow stops. Keeping the rules in one place is what makes those messages
identical across actions, and stops one of them quietly drifting into accepting
something the others refuse.
"""

import ipaddress
import re
from urllib.parse import urlsplit

ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})
HASH_LENGTHS: dict[int, str] = {32: "MD5", 40: "SHA1", 64: "SHA256"}
HEX = re.compile(r"\A[0-9a-fA-F]+\Z")
LABEL = re.compile(r"\A[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\Z")


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

    for test, description in (
        (parsed.is_loopback, "loopback"),
        (parsed.is_link_local, "link-local"),
        (parsed.is_private, "private"),
        (parsed.is_reserved, "reserved"),
    ):
        if test:
            return f"'{value}' is a {description} address and will not be sent to PolySwarm's public community"

    return None


def invalid_url_reason(value: str) -> str | None:
    """Why a URL is refused, or None when its scheme is one PolySwarm understands."""
    if urlsplit(value).scheme.lower() not in ALLOWED_SCHEMES:
        return f"'{value}' does not use the http or https scheme"
    return None


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
