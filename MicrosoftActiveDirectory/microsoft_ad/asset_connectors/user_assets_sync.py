from collections.abc import Generator
from functools import cached_property
from typing import Any

import requests
from ldap3.core.results import (
    RESULT_ADMIN_LIMIT_EXCEEDED,
    RESULT_UNAVAILABLE_CRITICAL_EXTENSION,
    RESULT_UNWILLING_TO_PERFORM,
)
from sekoia_automation.asset_connector.models.connector import AssetList
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel
from tenacity import RetryCallState, Retrying, stop_before_delay, stop_when_event_set, wait_exponential
from tenacity.wait import wait_base

from microsoft_ad.asset_connectors.exceptions import (
    AssetConnectorCriticalError,
    AssetConnectorPushError,
    AssetConnectorSearchError,
    AssetConnectorStoppedError,
    RetryableStatusError,
)
from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector
from microsoft_ad.helpers import retry_after_seconds, sort_control

RETRYABLE_STATUS = {408, 429}


def raise_on_retryable_status(response: requests.Response, *args: Any, **kwargs: Any) -> None:
    if response.status_code in RETRYABLE_STATUS or response.status_code >= 500:
        raise RetryableStatusError(f"HTTP {response.status_code} from {response.url}", response=response)


class wait_retry_after(wait_base):
    """Wait for the `Retry-After` of a transient error answer, or fall back to `fallback`."""

    def __init__(self, fallback: wait_base) -> None:
        self.fallback = fallback

    def __call__(self, retry_state: RetryCallState) -> float:
        error = retry_state.outcome.exception() if retry_state.outcome else None
        if isinstance(error, RetryableStatusError) and error.response is not None:
            delay = retry_after_seconds(error.response.headers.get("Retry-After"))
            if delay is not None:
                return delay
        return self.fallback(retry_state)


class MicrosoftADUserAssetSyncConnector(MicrosoftADUserAssetConnector):
    """
    Variant of the user asset connector that runs a single, interruptible fetch
    cycle, so it can be driven by an action (e.g. on an on-premise runner).

    The users are read sorted by `whenCreated` (server-side sort control), so the
    checkpoint, the most recent `whenCreated` read, can be committed after each pushed
    batch like the cloud connector: no user left to read is older than it, and an
    interrupted cycle resumes from the last pushed batch.

    If the directory refuses to sort, the users come in directory order: a checkpoint
    committed in the middle of the cycle could then skip older users not read yet, so
    it is only committed once the whole directory has been read and pushed.

    TODO: drop this class and use
    `sekoia_automation.asset_connector.AssetConnectorAction` once
    https://github.com/SEKOIA-IO/sekoia-automation-sdk/pull/291 is released.
    """

    # Maximum time spent retrying a push to Sekoia.io
    PUSH_RETRY_MAX_DELAY = 300

    # LDAP result codes of a directory that refuses the sort control
    SORT_REFUSED_RESULTS = {
        RESULT_ADMIN_LIMIT_EXCEEDED,
        RESULT_UNAVAILABLE_CRITICAL_EXTENSION,
        RESULT_UNWILLING_TO_PERFORM,
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cycle_stats = {"fetched": 0, "pushed_batches": 0, "failed_batches": 0}
        self._cycle_complete = False
        # Whether the users are read sorted by `whenCreated` in this cycle
        self.sorted_search = False

    def _retry(self) -> Retrying:  # type: ignore[override]
        return Retrying(
            # Give up instead of waiting past the delay, e.g. for a `Retry-After` longer than the time left
            stop=stop_before_delay(self.PUSH_RETRY_MAX_DELAY) | stop_when_event_set(self._stop_event),
            wait=wait_retry_after(fallback=wait_exponential(multiplier=1, min=1, max=10)),
            # Wake up as soon as the connector is stopped, instead of sleeping the whole wait
            sleep=self._stop_event.wait,
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

    def _run_paged_search(
        self, controls: list[tuple[str, bool, bytes]] | None = None
    ) -> Generator[dict[str, Any], None, None]:
        sorted_entries = super()._run_paged_search(controls=[*(controls or []), sort_control("whenCreated")])
        # The first page runs the search: a refused sort returns no entry and an error result
        first_entry = next(sorted_entries, None)
        if first_entry is None and self._sort_refused():
            self.sorted_search = False
            self.log(
                message="The directory refused to sort the users by creation date: the checkpoint is only "
                "saved once the whole directory has been read, which may not fit in one run",
                level="warning",
            )
            yield from super()._run_paged_search(controls=controls)
            return

        self.sorted_search = True
        if first_entry is not None:
            yield first_entry
        yield from sorted_entries

    def _sort_refused(self) -> bool:
        result = getattr(self._ldap_client, "result", None) or {}
        return result.get("result") in self.SORT_REFUSED_RESULTS

    def update_checkpoint(self) -> None:
        # `post_assets_to_api` calls this method after each pushed batch: safe when the
        # users are read sorted, otherwise only at the end of a complete cycle
        if self.sorted_search or self._cycle_complete:
            super().update_checkpoint()

    def _ensure_cycle_can_go_on(self) -> None:
        if self._critical_log_sent:
            raise AssetConnectorCriticalError()
        if not self.running:
            raise AssetConnectorStoppedError()

    def _ensure_search_completed(self) -> None:
        result = getattr(self._ldap_client, "result", None)
        if isinstance(result, dict) and result.get("result", 0) != 0:
            raise AssetConnectorSearchError(
                f"The LDAP search stopped before its last page: {result.get('description')} ({result.get('result')})"
            )

    def asset_fetch_cycle(self) -> None:
        """Fetch assets from the connector and push them to Sekoia.io, once."""
        self.log(
            message=f"Starting a new asset fetch cycle for connector {self.connector_name}",
            level="info",
        )
        self.cycle_stats = {"fetched": 0, "pushed_batches": 0, "failed_batches": 0}
        self._cycle_complete = False
        self.sorted_search = False
        self.skipped_users = 0

        # TODO: use the generic AssetItem type once this cycle moves to the SDK
        # (https://github.com/SEKOIA-IO/sekoia-automation-sdk/pull/291)
        assets: list[UserOCSFModel] = []
        for asset in self.get_assets():
            # Check at each asset, not only before a push, to stop quickly once the
            # connector is stopped. The next run resumes from the last committed checkpoint.
            self._ensure_cycle_can_go_on()

            assets.append(asset)
            self.cycle_stats["fetched"] += 1

            if len(assets) >= self.batch_size:
                self._push_batch(assets)
                assets = []

        if assets:
            self._push_batch(assets)

        if self.skipped_users:
            self.log(
                message=f"{self.skipped_users} user(s) could not be mapped and were skipped: "
                "they will only be read again by a full resync",
                level="warning",
            )

        # The whole directory has been read and pushed: commit the checkpoint,
        # even if the connector was stopped after the last push
        if self._critical_log_sent:
            raise AssetConnectorCriticalError()
        self._ensure_search_completed()
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
            # TODO: drop this guard once `Trigger.log` no longer raises in the SDK
            try:
                self.log_exception(error, message="Unable to push a batch of assets to Sekoia.io")
            except Exception as log_error:
                self.log(f"Unable to send the push error log: {log_error}", level="warning")
            response = None

        if response is None:
            # Stop the cycle: the checkpoint must not move past the assets of this batch
            self.cycle_stats["failed_batches"] += 1
            raise AssetConnectorPushError()
        self.cycle_stats["pushed_batches"] += 1
