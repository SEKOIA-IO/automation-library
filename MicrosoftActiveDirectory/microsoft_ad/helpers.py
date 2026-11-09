import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from ldap3.core.exceptions import LDAPInvalidDnError
from ldap3.utils.dn import safe_dn

# Server-side sort control (RFC 2891), supported by Active Directory
SORT_REQUEST_CONTROL_OID = "1.2.840.113556.1.4.473"

DOMAIN_LABEL = re.compile(r"^[A-Za-z0-9-]+$")


def ber_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def sort_control(attribute: str, reverse: bool = False) -> tuple[str, bool, bytes]:
    """
    Build a critical server-side sort control on one attribute, for `paged_search(controls=...)`.

    The value is the BER encoding of SortKeyList ::= SEQUENCE OF SEQUENCE {
    attributeType OCTET STRING, orderingRule [0] OPTIONAL, reverseOrder [1] BOOLEAN DEFAULT FALSE }.
    Critical: the server fails the search instead of returning unsorted entries.
    """
    name = attribute.encode()
    key = b"\x04" + ber_length(len(name)) + name
    if reverse:
        key += b"\x81\x01\xff"
    sort_key = b"\x30" + ber_length(len(key)) + key
    return SORT_REQUEST_CONTROL_OID, True, b"\x30" + ber_length(len(sort_key)) + sort_key


def retry_after_seconds(value: str | None, now: datetime | None = None) -> float | None:
    """
    The delay asked by a `Retry-After` header, in seconds or as an HTTP date (RFC 9110),
    or None if the header is missing or invalid.
    """
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        date = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    return max(0.0, (date - (now or datetime.now(UTC))).total_seconds())


def basedn_error(basedn: str | None) -> str | None:
    if not basedn or not basedn.strip():
        return "A base DN is required to synchronize Active Directory users"
    if "=" in basedn:
        try:
            safe_dn(basedn)
        except LDAPInvalidDnError as error:
            return f"The base DN '{basedn}' is not a valid distinguished name: {error}"
        return None
    message = f"The base DN '{basedn}' is not a valid distinguished name"
    labels = basedn.strip().split(".")
    if len(labels) > 1 and all(DOMAIN_LABEL.match(label) for label in labels):
        suggestion = ",".join(f"DC={label}" for label in labels)
        message += f": use '{suggestion}' for the domain {basedn.strip()}"
    return message
