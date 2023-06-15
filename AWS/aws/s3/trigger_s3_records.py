import orjson

from aws.s3.queued import AWSS3QueuedConnector


class AWSS3RecordsTrigger(AWSS3QueuedConnector):
    name = "AWS S3 Records"

    def _parse_content(self, content: bytes) -> list:
        if len(content) == 0:
            return []

        records = []
        for record in orjson.loads(content).get("Records", []):
            if len(record) > 0:
                records.append(orjson.dumps(record).decode("utf-8"))

        return records
