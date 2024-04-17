"""Entry point for connectors."""

from sekoia_automation.loguru.config import init_logging
from sekoia_automation.module import Module

from connectors.azure_eventhub import AzureEventsHubTrigger
from connectors.blob.azure_blob import AzureBlobConnector
from connectors.blob.azure_key_vault import AzureKeyVaultConnector
from connectors.blob.azure_network_watcher import AzureNetworkWatcherConnector

if __name__ == "__main__":
    init_logging()

    module = Module()
    module.register(AzureEventsHubTrigger, "azure_eventhub_messages_trigger")
    module.register(AzureBlobConnector, "azure_blob_storage")
    module.register(AzureNetworkWatcherConnector, "azure_network_watcher")
    module.register(AzureKeyVaultConnector, "azure_key_vault")
    module.run()
