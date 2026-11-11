from urlscan_modules import UrlScanModule
from urlscan_modules.models import UrlScanModuleConfiguration


def test_configuration_defaults():
    configuration = UrlScanModuleConfiguration(api_key="key")
    assert configuration.base_url == "https://urlscan.io"


def test_module_fixture(module):
    assert isinstance(module, UrlScanModule)
    assert module.configuration.api_key == "test-api-key"
