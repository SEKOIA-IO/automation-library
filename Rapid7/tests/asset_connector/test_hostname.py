import pytest

from rapid7_insightvm.asset_connector.hostname import split_hostname


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("HOST01", ("host01", None)),
        ("  srv_01 ", ("srv_01", None)),
        ("ip-192-0-2-10.eu-west-1.compute.example.com", ("ip-192-0-2-10", "eu-west-1.compute.example.com")),
        ("srv-01.corp.example.fr", ("srv-01", "corp.example.fr")),
        # No public suffix: not a FQDN for the platform, kept whole
        ("host.local", ("host.local", None)),
        ("café", ("café", None)),
    ],
)
def test_split_hostname_usable(value, expected):
    assert split_hostname(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "Example Processor Module",
        "12345",
        "192.0.2.10",
        "a" * 64,
        ".example.com",
        "host..local",
    ],
)
def test_split_hostname_unusable(value):
    assert split_hostname(value) == (None, None)
