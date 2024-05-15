import json
from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration

EXCLUDED_EVENT_TYPES = [
    "File Modification",
    "File Scan",
    "Open Remote Process Handle",
    "Duplicate Process Handle",
    "Not Reported",
]


class DeepVisibilityConnector(AbstractAwsS3QueuedConnector):
    """Implementation of DeepVisibilityConnector."""

    configuration: AwsS3QueuedConfiguration
    name = "DeepVisibility AWS S3 Logs"

    def _parse_content(self, content: bytes) -> list[str]:
        """
        Parse the content of the object and return a list of records.

        Args:
            content:

        Returns:
            list[str]:
        """

        records = []
        for record in content.decode("utf-8").split("\n"):
            if len(record) > 0:
                try:
                    json_record = json.loads(record)
                    # Exclude events with no category defined or a group category
                    if "event.category" not in json_record or json_record["event.category"] == "group":
                        continue
                    # Exclude specific event types
                    if "event.type" in json_record and json_record["event.type"] in EXCLUDED_EVENT_TYPES:
                        continue
                    records.append(record)
                except:
                    pass

        return list(records)
