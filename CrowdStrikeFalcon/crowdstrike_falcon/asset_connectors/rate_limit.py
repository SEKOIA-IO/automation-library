import time

from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.connector import AssetList
from sekoia_automation.exceptions import AssetConnectorRateLimitError


class RateLimitedPushMixin(AssetConnector):
    """
    Pace the asset pushes and retry the ones refused by the Sekoia.io rate limit.
    """

    RATE_LIMIT_RETRY_WAIT: float = 60.0
    MAX_RATE_LIMIT_RETRIES: int = 10
    MIN_PUSH_INTERVAL: float = 1.0

    _last_push_at: float | None = None

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
        was accepted.
        """
        attempts = 0
        while self.running:
            self._wait_for_push_slot()
            if not self.running:
                break

            self._last_push_at = time.monotonic()
            try:
                return super().post_assets_to_api(assets=assets, asset_connector_api_url=asset_connector_api_url)
            except AssetConnectorRateLimitError as error:
                attempts += 1
                if attempts > self.MAX_RATE_LIMIT_RETRIES:
                    self.log(
                        f"Asset push still rate limited after {self.MAX_RATE_LIMIT_RETRIES} retries, giving up",
                        level="error",
                    )
                    raise

                wait = max(error.retry_after, self.RATE_LIMIT_RETRY_WAIT)
                self.log(
                    f"Asset push rate limited (attempt {attempts}/{self.MAX_RATE_LIMIT_RETRIES}), "
                    f"retrying in {wait} seconds",
                    level="warning",
                )
                self._stop_event.wait(wait)

        self.log("Connector stopped before the assets were pushed", level="warning")
        return None
