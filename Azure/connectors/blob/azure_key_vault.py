"""Default Azure Key Vault connector."""

import orjson

from connectors.blob import AbstractAzureBlobConnector


class AzureKeyVaultConnector(AbstractAzureBlobConnector):
    """Azure Key Vault connector."""

    name = "AzureKeyVaultConnector"

    def filter_blob_data(self, data: str) -> list[str]:
        """
        Extract key vault events from log message.

        Args:
            data: str

        Returns:
            list[dict[str, Any]]:
        """
        try:
            result = orjson.loads(data).get("records", [])
        except orjson.JSONDecodeError:
            result = [orjson.loads(value) for value in data.split("\n") if value != ""]

        return [orjson.dumps(value).decode("utf-8") for value in result]
