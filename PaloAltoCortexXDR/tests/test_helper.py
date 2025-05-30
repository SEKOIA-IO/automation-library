import pytest

from cortex_module.helper import format_fqdn, handle_fqdn


@pytest.mark.parametrize(
    "input_fqdn, expected",
    [
        # handle_fqdn tests
        ("https://example.com", "https://example.com/public_api/v1/alerts/get_alerts_multi_events"),
        ("https://example.com/", "https://example.com/public_api/v1/alerts/get_alerts_multi_events"),
        (
            "https://example.com/public_api/v1/alerts/get_alerts_multi_events",
            "https://example.com/public_api/v1/alerts/get_alerts_multi_events",
        ),
        (
            "https://example.com/public_api/v1/alerts/get_alerts_multi_events/",
            "https://example.com/public_api/v1/alerts/get_alerts_multi_events",
        ),
        ("api-example.com", "https://api-example.com/public_api/v1/alerts/get_alerts_multi_events"),
        ("example.com", "https://api-example.com/public_api/v1/alerts/get_alerts_multi_events"),
    ],
)
def test_handle_fqdn(input_fqdn, expected):
    assert handle_fqdn(input_fqdn) == expected


@pytest.mark.parametrize(
    "input_fqdn, expected",
    [
        ("https://example.com", "https://example.com"),
        ("api-example.com", "https://api-example.com"),
        ("example.com", "https://api-example.com"),
    ],
)
def test_format_fqdn(input_fqdn, expected):
    assert format_fqdn(input_fqdn) == expected
