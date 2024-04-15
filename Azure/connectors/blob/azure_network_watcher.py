"""Default Azure Key Vault connector."""

from datetime import timezone

import orjson
from dateutil.parser import isoparse

from connectors.blob import AbstractAzureBlobConnector


class AzureNetworkWatcherConnector(AbstractAzureBlobConnector):
    """Azure Network Watcher connector."""

    name = "AzureNetworkWatcherConnector"

    def filter_blob_data(self, data: str) -> list[str]:
        """
        Format blob data.

        Main purpose of this function is to format input data to supported intake format:
            https://learn.microsoft.com/en-us/azure/network-watcher/vnet-flow-logs-overview

        Args:
            data: dict[Any, Any]
            time_filter: datetime | None

        Returns:
            list[dict[Any, Any]]:
        """
        modified_result = []
        time_filter = self.last_event_date
        for line in orjson.loads(data).get("records", []):
            line_time = isoparse(line["time"]).astimezone(timezone.utc)

            # If the record is too old, ignore it.
            if time_filter and line_time < time_filter:
                continue

            result = {
                "macAddress": line["macAddress"],
                "operationName": line["operationName"],
                "resourceId": line["resourceId"],
                "time": line["time"],
            }

            for property_flow in line["properties"]["flows"]:
                result["rule"] = property_flow["rule"]

                for flow in property_flow["flows"]:
                    for flow_tuple in flow["flowTuples"]:
                        result["flow.0"] = flow_tuple

            modified_result.append(result)

        return [orjson.dumps(value).decode("utf-8") for value in modified_result]
