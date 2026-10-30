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

    description = non_public(parsed)
    if description:
        return f"'{value}' is a {description} address and will not be sent to {_PUBLIC}"
    return None


def non_public(parsed: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
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
        return f"'{without_credentials(value)}' is not a valid URL"

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        return f"'{without_credentials(value)}' does not use the http or https scheme"

    if "\\" in _authority(value):
        return (
            f"'{without_credentials(value)}' has a backslash in its host part, which parsers read differently, "
            f"and will not be sent to {_PUBLIC}"
        )

    # Report the host, not the URL, wherever there is one: a URL can carry a
    # username and password, and a refusal is written to the playbook log.
    if not host:
        return f"'{without_credentials(value)}' has no host"
    host = host.rstrip(".").lower()

    # A browser style parser may read a different host than urlsplit does. Work
    # it out the WHATWG way and refuse the URL when the two disagree, so the
    # host we check is the host the engine fetches.
    if _whatwg_host(value) != host:
        return (
            f"'{without_credentials(value)}' is read as a different host by different parsers "
            f"and will not be sent to {_PUBLIC}"
        )

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
        description = non_public(ipaddress.ip_address(host))
        if description:
            return f"The URL points at a {description} address '{host}' and will not be sent to {_PUBLIC}"
        return None

    if _is_internal_name(host) or "." not in host:
        return f"The host '{host}' only exists inside a network and will not be sent to {_PUBLIC}"

    return None


def _authority(value: str) -> str:
    """The text between '//' and the first slash, backslash, question mark or hash."""
    rest = value.strip().partition("//")[2]
    return re.split(r"[/\\?#]", rest, maxsplit=1)[0]


def _whatwg_host(value: str) -> str:
    """The host a WHATWG parser takes from a URL: after the last '@', before any port."""
    hostport = _authority(value).rpartition("@")[2]
    if hostport.startswith("["):
        host = hostport[1:].partition("]")[0]
    else:
        host = hostport.partition(":")[0]
    return host.rstrip(".").lower()


def _is_internal_name(host: str) -> bool:
    """True for a lower case hostname the standards reserve for use inside a network.

    The one rule behind both the URL and the domain checks, so a name that is
    refused as part of a URL cannot be accepted on its own.
    """
    return host == "localhost" or host.endswith(PRIVATE_SUFFIXES)


def without_credentials(value: str) -> str:
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
    # Same check as the URL path: 127.1, 10.1.1, 0x7f.1 and 192.168.001.001 are
    # not literals to ipaddress but connect to the address they spell. A name
    # with any non-numeric label, such as 123.example.com, is not affected.
    try:
        socket.inet_aton(candidate)
    except OSError:
        pass
    else:
        return (
            f"'{value}' is an IP address written in an unusual form, not a domain. "
            f"Use the {ip_action} action for an address"
        )
    if _is_internal_name(candidate.lower()):
        return f"'{candidate}' is a name that only exists inside a network and will not be sent to {_PUBLIC}"

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


def invalid_imphash_reason(value: str) -> str | None:
    """Why an import hash is refused, or None when it is 32 hexadecimal characters.

    An imphash is an MD5 of a file's import table, so it has the shape of an
    MD5 and nothing else.
    """
    candidate = value.strip()
    if not candidate:
        return "no import hash was supplied"
    if len(candidate) != 32 or not HEX.match(candidate):
        return f"'{value}' is not a plausible imphash: expected 32 hexadecimal characters"
    return None


def hash_kind(value: str) -> str | None:
    """The hash algorithm a value could be, or None when it is not a hash."""
    return HASH_LENGTHS.get(len(value.strip())) if HEX.match(value.strip() or " ") else None
