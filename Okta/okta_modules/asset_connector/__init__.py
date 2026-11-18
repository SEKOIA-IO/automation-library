import asyncio

from sekoia_automation.asset_connector import AsyncAssetConnector


class OktaAsyncAssetConnector(AsyncAssetConnector):
    """Asset connector base of the Okta module."""

    def run(self) -> None:
        """Run the async main loop in a new event loop.

        The SDK gets the current event loop, which Python 3.14 no longer creates in the main thread:
        the connector stopped at start with "There is no current event loop in thread 'MainThread'".
        """
        asyncio.run(self.async_run())
