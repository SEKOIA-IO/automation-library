import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sekoia_automation.module import Module

from okta_modules.asset_connector.device_assets import OktaDeviceAssetConnector
from okta_modules.asset_connector.user_assets import OktaUserAssetConnector


@pytest.mark.parametrize("connector_class", [OktaDeviceAssetConnector, OktaUserAssetConnector])
def test_run_starts_without_a_current_event_loop(connector_class, data_storage):
    """Python 3.14 creates no event loop in the main thread: run() must start one itself"""
    module = Module()
    module.configuration = {"base_url": "https://example.com", "apikey": "fake_okta_api_key"}
    connector = connector_class(module=module, data_path=data_storage)
    connector.log = Mock()
    try:
        previous_loop = asyncio.get_event_loop()
    except RuntimeError:
        previous_loop = None
    asyncio.set_event_loop(None)

    try:
        with patch.object(connector_class, "async_run", new_callable=AsyncMock) as async_run:
            connector.run()
    finally:
        # The other tests keep the event loop they had
        asyncio.set_event_loop(previous_loop)

    async_run.assert_awaited_once()
