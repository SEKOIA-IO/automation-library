import pytest

from akamai_modules.models import AkamaiModuleConfiguration


@pytest.mark.parametrize(
    "host,expected_base_url",
    [
        ("http://example.com/", "https://example.com"),
        ("https://example.com/", "https://example.com"),
        ("example.com", "https://example.com"),
    ],
)
def test_base_url_normalization(host, expected_base_url):
    cfg = AkamaiModuleConfiguration(
        host=host,
        client_token="token",
        client_secret="secret",
        access_token="access",
    )

    assert cfg.base_url == expected_base_url
