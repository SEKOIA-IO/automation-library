"""Default Azure Key Vault connector."""

from datetime import timezone

import orjson
from dateutil.parser import isoparse

from connectors.blob import AbstractAzureBlobConnector


class AzureFlowLogsConnector(AbstractAzureBlobConnector):
    """Azure Network Watcher connector."""

    name = "AzureFlowLogsConnector"

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

        for record in orjson.loads(data).get("records", []):
            record_time = isoparse(record["time"]).astimezone(timezone.utc)

            # If the record is too old, ignore it.
            if time_filter and record_time < time_filter:
                continue

            result = {
                "time": record_time,
                "flowLogVersion": record["flowLogVersion"],
                "flowLogGUID": record["flowLogGUID"],
                "macAddress": record["macAddress"],
                "operationName": record["operationName"],
            }

            for flow in record.get("flowRecords", {}).get("flows", []):
                for group in flow.get("flowGroups", []):
                    for entry in group.get("flowTuples", []):
                        modified_result.append({
                            **result,
                            "aclID": flow["aclID"],
                            "rule": group["rule"],
                            "flow.0": entry
                        })

        return [orjson.dumps(value).decode("utf-8") for value in modified_result]
