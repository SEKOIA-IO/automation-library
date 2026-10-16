# Server-side sort control (RFC 2891), supported by Active Directory
SORT_REQUEST_CONTROL_OID = "1.2.840.113556.1.4.473"


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
