import importlib

from akamai_modules.models import AkamaiModuleConfiguration


def test_base_url_converts_http_to_https_and_trims_trailing_slash():
    cfg = AkamaiModuleConfiguration(
        host="http://example.com/",
        client_token="token",
        client_secret="secret",
        access_token="access",
    )

    assert cfg.base_url == "https://example.com"
