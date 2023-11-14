from zscaler.block_ioc import ZscalerBlockIOC


def test_block_ioc_action_success():
    action = ZscalerBlockIOC()
    action.module.configuration = {
        "base_url": "zscalerbeta.net",
        "api_key": "EqusKSwWRW7M",
        "username": "admin@16411777.zscalerbeta.net",
        "password": "xJO$c>(6I;)2",
    }

    result = action.run({"IoC": "185.216.70.222"})
    assert result == 204
