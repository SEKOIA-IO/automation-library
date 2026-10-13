from sekoia_automation.asset_connector import AssetConnectorAction

from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector


class MicrosoftADUserAssetsOnPremiseAction(AssetConnectorAction):
    """Run one collection cycle of the user asset connector, e.g. on an on-premise runner."""

    connector_class = MicrosoftADUserAssetConnector
