import pytest

from trendmicro_modules.models import TrendMicroModuleConfiguration


@pytest.mark.parametrize(
    "config_kwargs",
    [
        {},
        {"foo": "bar"},
    ],
)
def test_trendmicro_module_configuration_instantiation(config_kwargs):
    config = TrendMicroModuleConfiguration(**config_kwargs)
    assert config.dict() == {}
