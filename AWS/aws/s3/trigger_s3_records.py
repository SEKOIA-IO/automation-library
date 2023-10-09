import orjson

from aws.s3.queued import AWSS3QueuedConnector


class AWSS3RecordsTrigger(AWSS3QueuedConnector):
    name = "AWS S3 Records"

    @staticmethod
    def is_valid_payload(payload: dict) -> bool:  # pragma: no cover
        event_source = payload.get("eventSource")

        if event_source is "s3.amazonaws.com" and filter(
            lambda x: x in payload.get("eventName"),
            ["Delete", "Create", "Copy", "Put", "Restore", "GetObject", "GetObjectTorrent", "ListBuckets"],
        ):
            return True

        if event_source != "s3.amazonaws.com" and filter(
            lambda x: x in payload.get("eventName"), ["List", "Describe"]
        ):
            return True

        return False

    def _parse_content(self, content: bytes) -> list:
        if len(content) == 0:
            return []

        records = []
        for data in orjson.loads(content).get("Records", []):
            if len(data) > 0:
                # https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-examples.html
                # Go through each element in list and add to result_data if it is a valid payload based on this
                # https://github.com/SEKOIA-IO/automation-library/issues/346
                result_data = [result for result in data if self.is_valid_payload(result)]  # pragma: no cover
                records.append(orjson.dumps(result_data).decode("utf-8"))

        return records
