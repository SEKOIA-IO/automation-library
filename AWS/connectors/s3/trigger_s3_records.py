"""Contains AwsS3RecordsTrigger."""

from typing import Any

import orjson

from connectors.s3 import AbstractAwsS3QueuedConnector


class AwsS3RecordsTrigger(AbstractAwsS3QueuedConnector):
    """Implementation of AwsS3RecordsTrigger."""

    name = "AWS S3 Records"

    _events_prefixes = {
        "s3.amazonaws.com": {
            # If eventSource is "s3" then we should collect logs only if the event name starts with one of the following
            "supported": [
                "Delete",
                "Create",
                "Copy",
                "Put",
                "Restore",
                "GetObjectTorrent",
                "ListBuckets",
            ],
            # If it is one of the unsupported events, we should skip it
            "unsupported": ["GetObjectTagging"],
        },
        "ec2.amazonaws.com": {
            # If it is one of the unsupported events, we should skip it
            "unsupported": [
                "AssignPrivateIpAddresses",
                "CreateTags",
                "DeleteTags",
                "DescribeAddresses",
                "DescribeInstances",
                "DescribeInstanceStatus",
                "DescribePublicIpv4Pools",
                "DescribeSubnets",
                "DescribeTags",
                "DescribeVolumes",
                "DescribeVpcs",
                "GetEbsDefaultKmsKeyId",
                "GetIpamPoolCidrs",
                "GetManagedPrefixListEntries",
            ],
        },
        "default": {"unsupported": ["List", "Describe", "GetRecords"]},
    }

    @classmethod
    def is_valid_payload(cls, payload: dict[str, Any]) -> bool:
        """
        Check if the payload is valid.

        Args:
            payload: dict[str, Any]

        Returns:
            bool:
        """
        event_source = payload.get("eventSource", "")
        event_name = payload.get("eventName", "")
        if event_source not in cls._events_prefixes.keys():
            event_source = "default"

        supported = cls._events_prefixes[event_source].get("supported", [])
        unsupported = cls._events_prefixes[event_source].get("unsupported", [])

        for prefix in unsupported:
            if event_name.startswith(prefix):
                return False

        for prefix in supported:
            if event_name.startswith(prefix):
                return True

        return len(supported) == 0 and len(unsupported) != 0

    async def _process_content(self, content: bytes) -> int:
        """
        Parse the content of the object and return a list of records.

        Args:
            content: bytes

        Returns:
            list[str]:
        """
        if len(content) == 0:
            return 0

        records = []
        total_count = 0
        for data in orjson.loads(content).get("Records", []):
            # https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-examples.html
            # Go through each element in list and add to result_data if it is a valid payload based on this
            # https://github.com/SEKOIA-IO/automation-library/issues/346
            if len(data) > 0 and self.is_valid_payload(data):
                records.append(orjson.dumps(data).decode("utf-8"))
                if len(records) >= self.limit_of_events_to_push:
                    total_count += len(await self.push_data_to_intakes(events=records))
                    records = []

        if records:
            total_count += len(await self.push_data_to_intakes(events=records))

        return total_count
