from netskope_modules.models import NetskopeModuleConfiguration


def test_module_configuration_base_url_is_optional():
    assert NetskopeModuleConfiguration().base_url is None


def test_module_configuration_with_base_url():
    configuration = NetskopeModuleConfiguration(base_url="https://tenant.goskope.com")

    assert configuration.base_url == "https://tenant.goskope.com"
