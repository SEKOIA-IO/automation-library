import os
import time

from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.connector import AssetList
from sekoia_automation.exceptions import AssetConnectorRateLimitError


class RateLimitedPushMixin(AssetConnector):
    """
    Pace the asset pushes, retry the ones refused by the Sekoia.io rate limit, and commit
    the checkpoint only once every batch of a cycle has been pushed.

    A rate-limited batch waits for the `Retry-After` given by Sekoia.io, or
    `RATE_LIMIT_RETRY_WAIT` seconds when the response carries none (overridable with the
    `ASSET_CONNECTOR_RATE_LIMIT_WAIT` env variable). A batch gives up, and the SDK loop
    takes over, after `MAX_RATE_LIMIT_RETRIES` retries or once it would have waited more
    than `MAX_TOTAL_RATE_LIMIT_WAIT` seconds.

    Subclasses must reset `_push_failed` to False when a new collection starts, and their
    `update_checkpoint` must do nothing while `_push_failed` is True.
    """

    RATE_LIMIT_RETRY_WAIT: float = 60.0
    MAX_RATE_LIMIT_RETRIES: int = 10
    MAX_TOTAL_RATE_LIMIT_WAIT: float = 3600.0
    MIN_PUSH_INTERVAL: float = 1.0

    _last_push_at: float | None = None
    _push_failed: bool = False

    @property
    def rate_limit_wait(self) -> float:
        """
        Wait (in seconds) after a 429 response without a usable `Retry-After` header.

        The SDK default (one hour) is far too long to retry a single batch, so it is
        replaced by `RATE_LIMIT_RETRY_WAIT`, unless `ASSET_CONNECTOR_RATE_LIMIT_WAIT` is set.
        """
        if wait := os.getenv("ASSET_CONNECTOR_RATE_LIMIT_WAIT"):
            try:
                return float(wait)
            except ValueError:
                self.log(
                    "Invalid ASSET_CONNECTOR_RATE_LIMIT_WAIT value; falling back to the default wait",
                    level="warning",
                )
        return self.RATE_LIMIT_RETRY_WAIT

    def _wait_for_push_slot(self) -> None:
        """Wait until the minimal delay since the previous push has elapsed."""
        if self._last_push_at is not None:
            delay = self.MIN_PUSH_INTERVAL - (time.monotonic() - self._last_push_at)
            if delay > 0:
                self._stop_event.wait(delay)

    def post_assets_to_api(self, assets: AssetList, asset_connector_api_url: str) -> dict[str, str] | None:
        """
        Push a batch, retrying it while it is refused by the rate limit.

        Returns None, like a failed push, when the connector is stopped before the batch
        was accepted. Any batch that does not make it through holds the checkpoint back.
        """
        attempts = 0
        waited = 0.0
        while self.running:
            self._wait_for_push_slot()
            if not self.running:
                break

            self._last_push_at = time.monotonic()
            try:
                response = super().post_assets_to_api(assets=assets, asset_connector_api_url=asset_connector_api_url)
            except AssetConnectorRateLimitError as error:
                attempts += 1
                wait = error.retry_after
                if attempts > self.MAX_RATE_LIMIT_RETRIES or waited + wait > self.MAX_TOTAL_RATE_LIMIT_WAIT:
                    self.log(
                        f"Asset push still rate limited after {attempts - 1} retries and {waited} seconds "
                        f"(limits: {self.MAX_RATE_LIMIT_RETRIES} retries, {self.MAX_TOTAL_RATE_LIMIT_WAIT} seconds), "
                        "giving up",
                        level="error",
                    )
                    self._push_failed = True
                    raise

                self.log(
                    f"Asset push rate limited (attempt {attempts}/{self.MAX_RATE_LIMIT_RETRIES}), "
                    f"retrying in {wait} seconds",
                    level="warning",
                )
                self._stop_event.wait(wait)
                waited += wait
                continue

            if response is None:
                # The batch was dropped, so the assets it carried were never ingested: hold
                # the checkpoint back so the next cycle collects them again.
                self._push_failed = True
            return response

        self.log("Connector stopped before the assets were pushed", level="warning")
        self._push_failed = True
        return None

    def asset_fetch_cycle(self) -> None:
        """Run a fetch cycle, then commit the checkpoint if it collected everything."""
        super().asset_fetch_cycle()
        # Every batch of the cycle has been pushed by now, so this is the first moment we
        # know the run was complete. An interrupted cycle raises and never gets here.
        if self.running and not self._push_failed:
            self.update_checkpoint()
