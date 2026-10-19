import json
import signal
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Timer
from typing import Any
from uuid import uuid4

from pydantic.v1 import BaseModel, Field
from sekoia_automation.storage import PersistentJSON

from microsoft_ad.actions_base import MicrosoftADAction
from microsoft_ad.asset_connectors.exceptions import AssetConnectorPushError, AssetConnectorStoppedError
from microsoft_ad.asset_connectors.user_assets_sync import MicrosoftADUserAssetSyncConnector


class SynchronizeAssetsArguments(BaseModel):
    """
    Arguments of the asset connector, plus the connector configuration to act for:
      * `asset_connector_uuid`: the connector configuration to push assets to.
      * `connector_configuration_token`: the token sending the connector logs.
    """

    asset_connector_uuid: str
    connector_configuration_token: str

    sekoia_base_url: str = "https://api.sekoia.io"
    sekoia_api_key: str
    basedn: str | None = None
    batch_size: int = Field(1000, ge=1)


class SynchronizeAssetsAction(MicrosoftADAction):
    """
    Run one fetch cycle of the Microsoft AD user asset connector as an action.

    TODO: replace this action with
    `sekoia_automation.asset_connector.AssetConnectorAction` once
    https://github.com/SEKOIA-IO/sekoia-automation-sdk/pull/291 is released.
    """

    name = "Synchronize AD assets"
    description = "Synchronize Active Directory users with Sekoia.io assets"

    connector_class: type[MicrosoftADUserAssetSyncConnector] = MicrosoftADUserAssetSyncConnector

    # The platform marks a run failed after 2 hours: keep time to stop cleanly.
    MAX_DURATION = 100 * 60

    # A live run stops at MAX_DURATION: holding the lock for longer means it was killed without releasing it
    LOCK_TTL = MAX_DURATION + 10 * 60
    LOCK_FILE = "sync_lock.json"

    def stop_on_time_limit(self, time_limit_reached: Event, connector: MicrosoftADUserAssetSyncConnector) -> None:
        time_limit_reached.set()
        connector.stop()

    @contextmanager
    def _warn_on_error(self, reason: str) -> Iterator[None]:
        """Run a best-effort step: log a warning instead of raising."""
        try:
            yield
        except Exception as error:
            self.log(f"Unable to {reason}: {error}", "warning")

    @contextmanager
    def _run_lock(self) -> Iterator[bool]:
        """
        Hold the run lock of the configuration in its storage, so a run started while another one
        is still running skips its cycle instead of pushing the same users again. Yield whether
        the lock was acquired.
        """
        run_id = str(uuid4())
        # A new PersistentJSON each time: it only reads the file once
        with PersistentJSON(self.LOCK_FILE, self.data_path) as lock:
            acquired = not lock.get("run_id") or lock.get("expires_at", 0) <= time.time()
            if acquired:
                lock.update(run_id=run_id, expires_at=time.time() + self.LOCK_TTL)
        try:
            yield acquired
        finally:
            if acquired:
                with self._warn_on_error("release the run lock"):
                    with PersistentJSON(self.LOCK_FILE, self.data_path) as lock:
                        # Never release the lock of another run, taken once ours expired
                        if lock.get("run_id") == run_id:
                            lock.clear()

    def run(self, arguments: SynchronizeAssetsArguments) -> dict[str, Any]:
        # The connector registers its own SIGINT/SIGTERM handlers: restore the
        # previous ones once done, the process may run other actions
        previous_handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
        try:
            return self._run_cycle(arguments)
        finally:
            for signum, handler in previous_handlers.items():
                if handler is not None:
                    signal.signal(signum, handler)

    def _run_cycle(self, arguments: SynchronizeAssetsArguments) -> dict[str, Any]:
        asset_connector_uuid = arguments.asset_connector_uuid
        token = arguments.connector_configuration_token
        configuration = arguments.dict(exclude={"asset_connector_uuid", "connector_configuration_token"})

        # Drives the push endpoint and the User-Agent of the connector
        self.module._connector_configuration_uuid = asset_connector_uuid

        connector = self.connector_class(module=self.module, data_path=self.data_path)
        connector.configuration = configuration  # type: ignore[assignment]
        connector._token = token
        base_url = (connector.configuration.sekoia_base_url or connector.production_base_url).rstrip("/")
        connector.logs_url = (  # type: ignore[misc]
            f"{base_url}/api/v1/symphony/connector-configurations/{asset_connector_uuid}/logs"
        )

        time_limit_reached = Event()

        stop_timer = Timer(self.MAX_DURATION, self.stop_on_time_limit, args=(time_limit_reached, connector))
        stop_timer.daemon = True
        stop_timer.start()
        connector._logs_timer.start()

        stats: Counter[str] = Counter()
        has_more = False
        try:
            if arguments.basedn:
                with self._run_lock(data_path) as acquired:
                    if acquired:
                        connector.asset_fetch_cycle()
                    else:
                        connector.log(
                            message="Another run of this configuration is still in progress: this run is skipped",
                            level="warning",
                        )
            else:
                basedn_error = "A base DN is required to synchronize Active Directory users"
                self.error(basedn_error)
                with self._warn_on_error("send the connector error log"):
                    connector.log(message=basedn_error, level="error")
        except AssetConnectorStoppedError:
            if time_limit_reached.is_set():
                reason = f"reached the time limit of {self.MAX_DURATION // 60} minutes"
            else:
                reason = "was stopped"
            if connector.sorted_search:
                resume = "the next run resumes from the last pushed batch"
            else:
                resume = "the checkpoint was not advanced and the next run restarts from the previous checkpoint"
            connector.log(
                message=f"The fetch cycle {reason} before reading the whole directory: {resume}",
                level="warning",
            )
            # Without the sort, a stop never moves the checkpoint: an immediate re-run would only redo the same work
            has_more = connector.sorted_search
        except AssetConnectorPushError:
            # Fail the run without raising, so the counters are still returned
            self.error("A batch of assets could not be pushed to Sekoia.io")
            connector.log(
                message="A batch of assets could not be pushed to Sekoia.io: the checkpoint was not "
                "advanced and the next scheduled run restarts from the previous checkpoint",
                level="warning",
            )
        except Exception as error:
            # An error log is sent at once and raises when the logs endpoint is down: keep the
            # real error. TODO: drop this guard once `Trigger.log` no longer raises in the SDK
            with self._warn_on_error("send the connector error log"):
                connector.log(
                    message=f"Error while running asset connector {connector.connector_name}: {error}",
                    level="error",
                )
            raise
        finally:
            stats.update(connector.cycle_stats)
            stop_timer.cancel()
            connector.stop()
            with self._warn_on_error("close the LDAP connection"):
                connector._reset_ldap_connection()
            with self._warn_on_error("send the connector logs"):
                connector._send_logs_to_api()

        return {
            "fetched": stats["fetched"],
            "pushed_batches": stats["pushed_batches"],
            "failed_batches": stats["failed_batches"],
            "has_more": has_more,
        }
