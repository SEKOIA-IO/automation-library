import os
import pytest
from zscaler.block_ioc import ZscalerBlockIOC, ZscalerUnBlockIOC, ZscalerPushIOCBlock, ZscalerListBLockIOC


@pytest.mark.skipif(
    "{'ZSCALER_BASE_URL', 'ZSCALER_API_KEY', 'ZSCALER_USERNAME', 'ZSCALER_PASSWORD'}"
    ".issubset(os.environ.keys()) == False"
)
def test_block_ioc_action_success():
    ZSCALER_TEST_TENANT_CONF = {
        "base_url": os.environ["ZSCALER_BASE_URL"],
        "api_key": os.environ["ZSCALER_API_KEY"],
        "username": os.environ["ZSCALER_USERNAME"],
        "password": os.environ["ZSCALER_PASSWORD"],
    }

    IOC_to_test = "megapromonet.com"
    action = ZscalerBlockIOC()
    action.module.configuration = ZSCALER_TEST_TENANT_CONF
    action.run({"IoC": IOC_to_test})

    verif = ZscalerListBLockIOC()
    verif.module.configuration = ZSCALER_TEST_TENANT_CONF
    response = verif.run()
    if IOC_to_test in response["blacklistUrls"]:
        response = "ok"
    assert response == "ok"


@pytest.mark.skipif(
    "{'ZSCALER_BASE_URL', 'ZSCALER_API_KEY', 'ZSCALER_USERNAME', 'ZSCALER_PASSWORD'}"
    ".issubset(os.environ.keys()) == False"
)
def test_push_ioc_action_success():
    ZSCALER_TEST_TENANT_CONF = {
        "base_url": os.environ["ZSCALER_BASE_URL"],
        "api_key": os.environ["ZSCALER_API_KEY"],
        "username": os.environ["ZSCALER_USERNAME"],
        "password": os.environ["ZSCALER_PASSWORD"],
    }

    action = ZscalerPushIOCBlock()
    action.module.configuration = ZSCALER_TEST_TENANT_CONF
    action.run({"stix_objects_path": "./stix_object.json"})

    verif = ZscalerListBLockIOC()
    verif.module.configuration = ZSCALER_TEST_TENANT_CONF
    response = verif.run()
    if "77.91.78.118" in response["blacklistUrls"]:
        response = "ok"
    assert response == "ok"


@pytest.mark.skipif(
    "{'ZSCALER_BASE_URL', 'ZSCALER_API_KEY', 'ZSCALER_USERNAME', 'ZSCALER_PASSWORD'}"
    ".issubset(os.environ.keys()) == False"
)
def test_unblock_ioc_action_success():
    ZSCALER_TEST_TENANT_CONF = {
        "base_url": os.environ["ZSCALER_BASE_URL"],
        "api_key": os.environ["ZSCALER_API_KEY"],
        "username": os.environ["ZSCALER_USERNAME"],
        "password": os.environ["ZSCALER_PASSWORD"],
    }

    IOC_to_test = "megapromonet.com"
    action = ZscalerUnBlockIOC()
    action.module.configuration = ZSCALER_TEST_TENANT_CONF
    action.run({"IoC": IOC_to_test})

    verif = ZscalerListBLockIOC()
    verif.module.configuration = ZSCALER_TEST_TENANT_CONF
    response = verif.run()
    if IOC_to_test not in response["blacklistUrls"]:
        response = "ok"
    assert response == "ok"
