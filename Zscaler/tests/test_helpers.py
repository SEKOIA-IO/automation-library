# test_stix_indicator.py

from zscaler.helpers import is_a_supported_stix_indicator, stix_to_indicators


def test_supported_stix_indicator():
    stix_object = {"type": "indicator", "pattern_type": "stix"}
    assert is_a_supported_stix_indicator(stix_object) == True


def test_unsupported_indicator_type():
    stix_object = {"type": "not_an_indicator", "pattern_type": "stix"}
    assert is_a_supported_stix_indicator(stix_object) == False


def test_non_stix_pattern_type():
    stix_object = {"type": "indicator", "pattern_type": "not_stix"}
    assert is_a_supported_stix_indicator(stix_object) == False


def test_missing_pattern_type():
    stix_object = {
        "type": "indicator"
        # "pattern_type" key is missing
    }
    assert is_a_supported_stix_indicator(stix_object) == True


def test_supported_stix_conversion():
    stix_object = {"type": "indicator", "pattern": "[ipv4-addr:value = '192.168.1.1']", "pattern_type": "stix"}
    supported_types_map = {"ipv4-addr": {"value": "ipv4"}}
    expected_result = [{"type": "ipv4-addr", "value": "192.168.1.1"}]
    assert stix_to_indicators(stix_object, supported_types_map) == expected_result


def test_unsupported_stix_conversion():
    stix_object = {"type": "indicator", "pattern": "[domain-name:value = 'example.com']", "pattern_type": "stix"}
    supported_types_map = {"ipv4-addr": {"value": "ipv4"}}
    assert stix_to_indicators(stix_object, supported_types_map) == []


def test_empty_stix_object():
    stix_object = {}
    supported_types_map = {"ipv4-addr": {"value": "ipv4"}}
    assert stix_to_indicators(stix_object, supported_types_map) == []


def test_invalid_stix_object():
    stix_object = {"type": "not_an_indicator", "pattern": "[ipv4-addr:value = '192.168.1.1']", "pattern_type": "stix"}
    supported_types_map = {"ipv4-addr": {"value": "ipv4"}}
    assert stix_to_indicators(stix_object, supported_types_map) == []


def test_supported_types_map_not_found():
    stix_object = {"type": "indicator", "pattern": "[ipv4-addr:value = '192.168.1.1']", "pattern_type": "stix"}
    supported_types_map = {"domain-name": {"value": "domain"}}
    assert stix_to_indicators(stix_object, supported_types_map) == []
