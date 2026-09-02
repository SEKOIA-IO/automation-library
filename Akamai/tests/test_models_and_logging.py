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


def test_logging_module_configures_and_returns_logger(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "10")

    import akamai_modules.logging as logging_module

    logging_module = importlib.reload(logging_module)

    logger = logging_module.get_logger("akamai_waf_logs")

    assert logger is not None
