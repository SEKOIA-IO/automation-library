import pytest

from harfanglab.helpers import handle_uri, is_a_supported_stix_indicator, stix_to_indicators


def test_handle_uri():
    assert handle_uri("http://example.com") == "https://example.com"
    assert handle_uri("https://example.com/") == "https://example.com"
    assert handle_uri("example.com") == "https://example.com"
    assert handle_uri("https://example.com/path/to/resource") == "https://example.com/path/to/resource"
    assert handle_uri("http://example.com/path/to/resource") == "https://example.com/path/to/resource"
    assert handle_uri("example.com/path/to/resource") == "https://example.com/path/to/resource"


SUPPORTED_TYPES_MAP = {
    "ipv4-addr": {"value": "ip_both"},
    "file": {"hashes.MD5": "hash"},
}


def test_is_a_supported_stix_indicator():
    assert is_a_supported_stix_indicator({"type": "indicator", "pattern_type": "stix"}) is True
    assert is_a_supported_stix_indicator({"type": "indicator"}) is True
    assert is_a_supported_stix_indicator({"type": "indicator", "pattern_type": "yara"}) is False
    assert is_a_supported_stix_indicator({"type": "malware"}) is False


def test_stix_to_indicators_unsupported_object():
    assert stix_to_indicators({"type": "malware"}, SUPPORTED_TYPES_MAP) == []


@pytest.mark.parametrize(
    "pattern",
    [
        "[email-addr:value = 'a@b.c']",  # unsupported observable type
        "[file:extensions.'a'.b[*].c = 'x']",  # wildcard in path
        "[file:name = 'foo.exe']",  # unsupported path
        "[ipv4-addr:value != '1.2.3.4']",  # unsupported operator
    ],
)
def test_stix_to_indicators_skips_unsupported_comparisons(pattern):
    stix_object = {"type": "indicator", "pattern_type": "stix", "pattern": pattern}

    assert stix_to_indicators(stix_object, SUPPORTED_TYPES_MAP) == []


def test_stix_to_indicators():
    stix_object = {
        "type": "indicator",
        "pattern_type": "stix",
        "pattern": "[ipv4-addr:value = '1.2.3.4'] OR [file:hashes.MD5 = 'd41d8cd98f00b204e9800998ecf8427e']",
    }

    assert stix_to_indicators(stix_object, SUPPORTED_TYPES_MAP) == [
        {"type": "ip_both", "value": "1.2.3.4"},
        {"type": "hash", "value": "d41d8cd98f00b204e9800998ecf8427e"},
    ]
