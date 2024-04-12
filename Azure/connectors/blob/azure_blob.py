"""Default Azure Blob Storage connector."""

from connectors.blob import AbstractAzureBlobConnector


class AzureBlobConnector(AbstractAzureBlobConnector):
    """Azure Blob Storage connector."""

    name = "AzureBlobConnector"

    def filter_blob_data(self, data: str) -> list[str]:
        """
        Filter blob data and exclude empty lines.

        Args:
            data: str

        Returns:
            list[dict[str, Any]]:
        """
        return [line for line in data.split("\n") if line != ""]
