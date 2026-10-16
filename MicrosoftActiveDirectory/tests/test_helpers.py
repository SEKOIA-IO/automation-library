from microsoft_ad.helpers import ber_length, sort_control


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
