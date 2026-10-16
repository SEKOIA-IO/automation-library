from functools import cached_property
from typing import Any

import requests
from sekoia_automation.asset_connector.models.connector import AssetList
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel
from tenacity import Retrying, stop_after_delay, stop_when_event_set, wait_exponential

from microsoft_ad.asset_connectors.exceptions import (
    AssetConnectorCriticalError,
    AssetConnectorPushError,
    AssetConnectorStoppedError,
    RetryableStatusError,
)
from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector


RETRYABLE_STATUS = {408, 429}


def raise_on_retryable_status(response: requests.Response, *args: Any, **kwargs: Any) -> None:
    if response.status_code in RETRYABLE_STATUS or response.status_code >= 500:
        raise RetryableStatusError(f"HTTP {response.status_code} from {response.url}", response=response)


class MicrosoftADUserAssetSyncConnector(MicrosoftADUserAssetConnector):
    """
    Variant of the user asset connector that runs a single, interruptible fetch
    cycle, so it can be driven by an action (e.g. on an on-premise runner).

    The checkpoint is committed only once the whole directory has been read and
    pushed: LDAP returns the users in directory order, not sorted by `whenCreated`,
    so a checkpoint committed in the middle of a cycle could skip older users that
    were not read yet. An interrupted cycle restarts from the previous checkpoint
    and pushes again the users already sent (the asset API upserts them by uid).

    TODO: drop this class and use
    `sekoia_automation.asset_connector.AssetConnectorAction` once
    https://github.com/SEKOIA-IO/sekoia-automation-sdk/pull/291 is released.
    """

    # Maximum time spent retrying a push to Sekoia.io
    PUSH_RETRY_MAX_DELAY = 300

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cycle_stats = {"fetched": 0, "pushed_batches": 0, "failed_batches": 0}
        self._cycle_complete = False

    def _retry(self) -> Retrying:  # type: ignore[override]
        return Retrying(
            stop=stop_after_delay(self.PUSH_RETRY_MAX_DELAY) | stop_when_event_set(self._stop_event),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )

    # TODO: drop this override once the SDK retries transient error answers in `post_assets_to_api`
    @cached_property
    def _http_session(self) -> requests.Session:
        # The SDK only retries a push on exceptions: raise on transient error answers
        # so they go through `_retry` too, instead of failing the batch at once
        session = requests.Session()
        session.headers.update(self._http_header)
        session.hooks["response"].append(raise_on_retryable_status)
        return session

    def update_checkpoint(self) -> None:
        if self._cycle_complete:
            super().update_checkpoint()

    def _ensure_cycle_can_go_on(self) -> None:
        if self._critical_log_sent:
            raise AssetConnectorCriticalError()
        if not self.running:
            raise AssetConnectorStoppedError()

    def asset_fetch_cycle(self) -> None:
        """Fetch assets from the connector and push them to Sekoia.io, once."""
        self.log(
            message=f"Starting a new asset fetch cycle for connector {self.connector_name}",
            level="info",
        )
        self.cycle_stats = {"fetched": 0, "pushed_batches": 0, "failed_batches": 0}
        self._cycle_complete = False

        # TODO: use the generic AssetItem type once this cycle moves to the SDK
        # (https://github.com/SEKOIA-IO/sekoia-automation-sdk/pull/291)
        assets: list[UserOCSFModel] = []
        for asset in self.get_assets():
            # Check at each asset, not only before a push, to stop quickly once the
            # connector is stopped. The checkpoint is not committed, so the next
            # run restarts from the previous checkpoint.
            self._ensure_cycle_can_go_on()

            assets.append(asset)
            self.cycle_stats["fetched"] += 1

            if len(assets) >= self.batch_size:
                self._push_batch(assets)
                assets = []

        if assets:
            self._push_batch(assets)

        # The whole directory has been read and pushed: commit the checkpoint,
        # even if the connector was stopped after the last push
        if self._critical_log_sent:
            raise AssetConnectorCriticalError()
        self._cycle_complete = True
        self.update_checkpoint()

    def _push_batch(self, assets: list[UserOCSFModel]) -> None:
        # Check a second time before pushing the batch in case the connector has been stopped
        self._ensure_cycle_can_go_on()

        batch = AssetList(version=self.OCSF_SCHEMA_VERSION, items=assets)
        # post_assets_to_api returns None on failure
        try:
            response = self.post_assets_to_api(batch, self.asset_connector_endpoint)
        except requests.RequestException as error:
            # The retries give up as soon as the connector is stopped: resume on the next run
            if not self.running:
                raise AssetConnectorStoppedError() from error
            self.log_exception(error, message="Unable to push a batch of assets to Sekoia.io")
            response = None

        if response is None:
            # Stop the cycle: the checkpoint must not move past the assets of this batch
            self.cycle_stats["failed_batches"] += 1
            raise AssetConnectorPushError()
        self.cycle_stats["pushed_batches"] += 1
