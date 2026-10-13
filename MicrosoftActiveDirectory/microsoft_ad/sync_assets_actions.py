import signal
from collections import Counter
from threading import Timer
from typing import Any

from pydantic.v1 import BaseModel

from microsoft_ad.actions_base import MicrosoftADAction
from microsoft_ad.asset_connectors.exceptions import AssetConnectorStoppedError
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
    basedn: str
    batch_size: int = 1000


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

    def run(self, arguments: SynchronizeAssetsArguments) -> dict[str, Any]:
        # The connector registers its own SIGINT/SIGTERM handlers: restore the
        # previous ones once done, the process may run other actions
        previous_handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
        try:
            return self._run_cycle(arguments)
        finally:
            for signum, handler in previous_handlers.items():
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

        stop_timer = Timer(self.MAX_DURATION, connector.stop)
        stop_timer.daemon = True
        stop_timer.start()
        connector._logs_timer.start()

        stats: Counter[str] = Counter()
        has_more = False
        try:
            connector.asset_fetch_cycle()
        except AssetConnectorStoppedError:
            connector.log(
                message="Fetch cycle stopped before its end, the next run resumes "
                "from the last committed checkpoint",
                level="warning",
            )
            has_more = True
        except Exception as error:
            connector.log(
                message=f"Error while running asset connector {connector.connector_name}: {error}",
                level="error",
            )
            raise
        finally:
            stats.update(connector.cycle_stats)
            stop_timer.cancel()
            connector.stop()
            try:
                connector._send_logs_to_api()
            except Exception as error:
                self.log(f"Unable to send the connector logs: {error}", "warning")

        return {
            "fetched": stats["fetched"],
            "pushed_batches": stats["pushed_batches"],
            "failed_batches": stats["failed_batches"],
            "has_more": has_more,
        }
