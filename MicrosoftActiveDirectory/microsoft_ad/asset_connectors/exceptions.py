from sekoia_automation.exceptions import AutomationSDKError

# TODO: drop this module and import these exceptions from
# sekoia_automation.exceptions once
# https://github.com/SEKOIA-IO/sekoia-automation-sdk/pull/291 is released.


class AssetConnectorStoppedError(AutomationSDKError):
    """Raised when an asset connector is stopped in the middle of a fetch cycle."""

    def __init__(self) -> None:
        super().__init__("Asset connector stopped during a fetch cycle")


class AssetConnectorPushError(AutomationSDKError):
    """Raised when a batch of assets could not be pushed to Sekoia.io."""

    def __init__(self) -> None:
        super().__init__("Unable to push a batch of assets to Sekoia.io")


class AssetConnectorCriticalError(AutomationSDKError):
    """Raised when an asset connector sent a critical log, a fatal error, in the middle of a fetch cycle."""

    def __init__(self) -> None:
        super().__init__("Asset connector stopped after a critical error")
