"""Entry point for the AzureBlob connector."""

from sekoia_automation.loguru.config import init_logging

from connector import AzureBlobStorageModule
from connector.pull_azure_blob_data import AzureBlobConnector

if __name__ == "__main__":
    init_logging()

    module = AzureBlobStorageModule()
    module.register(AzureBlobConnector, "azure-blob-storage")
    module.run()
