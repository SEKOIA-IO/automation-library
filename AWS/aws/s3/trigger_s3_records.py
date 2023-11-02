import orjson

from aws.s3.queued import AWSS3QueuedConnector


class AWSS3RecordsTrigger(AWSS3QueuedConnector):
    name = "AWS S3 Records"

    @staticmethod
    def is_valid_payload(payload: dict) -> bool:
        event_source = payload.get("eventSource")

        # If eventSource is "s3" then we should collect logs only if the event name starts with one of the following
        if event_source == "s3.amazonaws.com":
            if payload.get("eventName", "") == "GetObjectTagging":
                return False

            return (
                list(
                    filter(
                        lambda x: payload.get("eventName", "").startswith(x),
                        ["Delete", "Create", "Copy", "Put", "Restore", "GetObjectTorrent", "ListBuckets"],
                    )
                )
                != []
            )
        else:
            # If eventSource is not "s3" we should skipp all events that start with "List" or "Describe"
            return (
                list(filter(lambda x: payload.get("eventName", "").startswith(x), ["List", "Describe", "GetRecords"]))
                == []
            )

    def _parse_content(self, content: bytes) -> list:
        if len(content) == 0:
            return []

        records = []
        for data in orjson.loads(content).get("Records", []):
            # https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-examples.html
            # Go through each element in list and add to result_data if it is a valid payload based on this
            # https://github.com/SEKOIA-IO/automation-library/issues/346
            if len(data) > 0 and self.is_valid_payload(data):
                records.append(orjson.dumps(data).decode("utf-8"))

        return records
