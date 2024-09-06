import string

from sentinelone_module.helpers import generate_password, is_a_supported_stix_indicator, stix_to_indicators


def assert_password(password: str):
    assert len(password) >= 10, "The length of the password is lesser than 10"
    assert sum(c.islower() for c in password) > 0, "No lowercase character found"
    assert sum(c.isupper() for c in password) > 0, "No uppercase character found"
    assert sum(c.isdigit() for c in password) > 0, "No digit character found"
    assert sum(1 if c in string.punctuation else 0 for c in password) > 0, "No special character found"


def test_generate_password():
    assert_password(generate_password())
    assert_password(generate_password(6))


def test_is_a_supported_stix_indicator():
    assert is_a_supported_stix_indicator({"type": "indicator", "pattern_type": "stix"})
    assert not is_a_supported_stix_indicator({"type": "indicator", "pattern_type": "not_stix"})
    assert not is_a_supported_stix_indicator({"type": "not_indicator", "pattern_type": "stix"})


def test_stix_to_indicators():
    supported_types_map = {
        "ipv4-addr": {"value": "IPV4"},
        "ipv6-addr": {"value": "IPV6"},
        "domain-name": {"value": "DNS"},
        "file": {"hashes.MD5": "MD5", "hashes.SHA1": "SHA1", "hashes.sha256": "SHA256"},
        "url": {"value": "URL"}
    }

    stix_object = {
        "type": "indicator",
        "pattern_type": "stix",
        "pattern": "[file:hashes.MD5 = '123456']"
    }

    assert stix_to_indicators(stix_object, supported_types_map) == [{"type": "MD5", "value": "123456"}]

    stix_object = {
        "type": "indicator",
        "pattern_type": "stix",
        "pattern": "[file:hashes.MD5 = '123456' AND file:hashes.SHA1 = 'abcdef']"
    }

    assert stix_to_indicators(stix_object, supported_types_map) == [
        {"type": "MD5", "value": "123456"},
        {"type": "SHA1", "value": "abcdef"}
    ]

    stix_object = {
        "type": "indicator",
        "pattern_type": "stix",
        "pattern": "[file:hashes.MD5 = '123456' AND file:hashes.SHA1 = 'abcdef' AND file:hashes.sha256 = 'abcdef']"
    }

    assert stix_to_indicators(stix_object, supported_types_map) == [
        {"type": "MD5", "value": "123456"},
        {"type": "SHA1", "value": "abcdef"},
        {"type": "SHA256", "value": "abcdef"}
    ]
