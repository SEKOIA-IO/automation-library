from typing import Any

from sekoia_automation.asset_connector.models.connector import AssetList
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel

from microsoft_ad.asset_connectors.exceptions import AssetConnectorPushError, AssetConnectorStoppedError
from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector


class MicrosoftADUserAssetSyncConnector(MicrosoftADUserAssetConnector):
    """
    Variant of the user asset connector that runs a single, interruptible fetch
    cycle, so it can be driven by an action (e.g. on an on-premise runner).

    TODO: drop this class and use
    `sekoia_automation.asset_connector.AssetConnectorAction` once
    https://github.com/SEKOIA-IO/sekoia-automation-sdk/pull/291 is released.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cycle_stats = {"fetched": 0, "pushed_batches": 0, "failed_batches": 0}

    def asset_fetch_cycle(self) -> None:
        """Fetch assets from the connector and push them to Sekoia.io, once."""
        self.log(
            message=f"Starting a new asset fetch cycle for connector {self.connector_name}",
            level="info",
        )
        self.cycle_stats = {"fetched": 0, "pushed_batches": 0, "failed_batches": 0}

        # TODO: use the generic AssetItem type once this cycle moves to the SDK
        # (https://github.com/SEKOIA-IO/sekoia-automation-sdk/pull/291)
        assets: list[UserOCSFModel] = []
        for asset in self.get_assets():
            
            # Check at each asset, not only before a push, to stop quickly once the
            # connector is stopped. The assets not pushed yet are dropped: the
            # checkpoint does not cover them, so the next run fetches them again.
            if not self.running:
                raise AssetConnectorStoppedError()

            assets.append(asset)
            self.cycle_stats["fetched"] += 1

            if len(assets) >= self.batch_size:
                self._push_batch(assets)
                assets = []

        if assets:
            self._push_batch(assets)

    def _push_batch(self, assets: list[UserOCSFModel]) -> None:
        # Check a second time before pushing the batch in case the connector has been stopped
        if not self.running:
            raise AssetConnectorStoppedError()

        batch = AssetList(version=self.OCSF_SCHEMA_VERSION, items=assets)
        # post_assets_to_api commits the checkpoint on success and returns None on failure
        response = self.post_assets_to_api(batch, self.asset_connector_endpoint)
        if response is not None:
            self.cycle_stats["pushed_batches"] += 1
        else:
            self.cycle_stats["failed_batches"] += 1
            # Going on would commit a checkpoint past the assets of this batch
            raise AssetConnectorPushError()
