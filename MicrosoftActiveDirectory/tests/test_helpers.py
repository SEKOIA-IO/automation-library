from datetime import UTC, datetime

import pytest

from microsoft_ad.helpers import basedn_error, ber_length, retry_after_seconds, sort_control


def test_sort_control_encodes_an_ascending_sort_on_when_created():
    oid, criticality, value = sort_control("whenCreated")

    assert oid == "1.2.840.113556.1.4.473"
    assert criticality is True
    # SEQUENCE { SEQUENCE { OCTET STRING "whenCreated" } }
    assert value == bytes.fromhex("300f300d040b") + b"whenCreated"
    assert (
        sort_control("whenCreated", reverse=True)[2]
        == bytes.fromhex("30123010040b") + b"whenCreated" + b"\x81\x01\xff"
    )


def test_ber_length_uses_the_long_form_from_128_bytes():
    assert ber_length(127) == bytes([0x7F])
    assert ber_length(128) == bytes([0x81, 0x80])
    assert ber_length(300) == bytes([0x82, 0x01, 0x2C])


@pytest.mark.parametrize(
    "value, expected",
    [
        ("30", 30.0),
        (" 0 ", 0.0),
        ("Fri, 16 Oct 2026 12:00:30 GMT", 30.0),
        # A date in the past: retry at once
        ("Fri, 16 Oct 2026 11:59:00 GMT", 0.0),
        (None, None),
        ("", None),
        ("-5", None),
        ("soon", None),
    ],
)
def test_retry_after_seconds(value, expected):
    assert retry_after_seconds(value, now=datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC)) == expected


@pytest.mark.parametrize("basedn", ["DC=example,DC=com", "OU=Users,DC=example,DC=com", "CN=a@b,DC=example,DC=com"])
def test_basedn_error_accepts_a_distinguished_name(basedn):
    assert basedn_error(basedn) is None


@pytest.mark.parametrize(
    "basedn, expected",
    [
        (None, "A base DN is required to synchronize Active Directory users"),
        ("  ", "A base DN is required to synchronize Active Directory users"),
        (
            " example.corp ",
            "The base DN ' example.corp ' is not a valid distinguished name: "
            "use 'DC=example,DC=corp' for the domain example.corp",
        ),
        ("admin@example.corp", "The base DN 'admin@example.corp' is not a valid distinguished name"),
        ("ad.example.com/", "The base DN 'ad.example.com/' is not a valid distinguished name"),
        ("https://ad.example.com", "The base DN 'https://ad.example.com' is not a valid distinguished name"),
        ("example", "The base DN 'example' is not a valid distinguished name"),
        (
            "DC=example, DC=com",
            "The base DN 'DC=example, DC=com' is not a valid distinguished name: "
            "character ' ' not allowed in attribute type",
        ),
    ],
)
def test_basedn_error_explains_an_invalid_base_dn(basedn, expected):
    assert basedn_error(basedn) == expected
