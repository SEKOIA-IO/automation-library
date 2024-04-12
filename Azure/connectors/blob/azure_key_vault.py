"""Default Azure Key Vault connector."""

from typing import Any

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
        result: list[dict[str, Any]] = orjson.loads(data).get("records", [])

        return [orjson.dumps(value).decode("utf-8") for value in result]
