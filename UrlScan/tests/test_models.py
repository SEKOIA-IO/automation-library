import pytest
from pydantic import ValidationError

from urlscan_modules import UrlScanModule
from urlscan_modules.models import ScanIdArguments, UrlScanModuleConfiguration


def test_configuration_defaults():
    configuration = UrlScanModuleConfiguration(api_key="key")
    assert configuration.base_url == "https://urlscan.io"


def test_module_fixture(module):
    assert isinstance(module, UrlScanModule)
    assert module.configuration.api_key == "test-api-key"


def test_arguments_must_be_an_object():
    with pytest.raises(ValidationError, match="valid dictionary"):
        ScanIdArguments.model_validate(["not", "an", "object"])
