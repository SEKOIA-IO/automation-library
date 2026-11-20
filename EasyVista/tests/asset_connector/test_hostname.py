import pytest

from easyvista_modules.asset_connector.hostname import split_hostname


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("HOST01", ("host01", None)),
        ("  srv_01 ", ("srv_01", None)),
        (
            "ec2-63-35-154-82.eu-west-1.compute.amazonaws.com",
            ("ec2-63-35-154-82", "eu-west-1.compute.amazonaws.com"),
        ),
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
        "BMXP342020 Modicon M340 Processor Module",
        "12345",
        "10.0.0.1",
        "a" * 64,
        ".example.com",
        "host..local",
    ],
)
def test_split_hostname_unusable(value):
    assert split_hostname(value) == (None, None)
