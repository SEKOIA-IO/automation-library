import time
from abc import ABCMeta, abstractmethod
from collections.abc import Generator
from functools import cached_property

import orjson
from sekoia_automation.connector import DefaultConnectorConfiguration

from aws.base import AWSConnector
from aws.utils import get_content, normalize_s3_key


class AWSS3Object:
    def __init__(self, client, bucket: str, key: str):
        self.client = client
        self.bucket = bucket
        self.key = normalize_s3_key(key)

    @staticmethod
    def from_record(client, record: dict) -> "AWSS3Object":
        s3 = record.get("s3", {})
        bucket = s3.get("bucket", {}).get("name")
        key = s3.get("object", {}).get("key")

        if bucket is None:
            raise ValueError("Bucket is undefined", record)

        if key is None:
            raise ValueError("Key is undefined", record)

        return AWSS3Object(client, bucket, key)

    def read(self) -> bytes:
        """
        Read the remote object
        """
        obj = self.client.get_object(Bucket=self.bucket, Key=self.key)
        return get_content(obj)


class AWSS3QueuedConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 10000
    delete_consumed_messages: bool = False
    queue_name: str


class AWSS3QueuedConnector(AWSConnector, metaclass=ABCMeta):
    configuration: AWSS3QueuedConfiguration

    @cached_property
    def sqs_client(self):
        return self.session.client("sqs")

    @cached_property
    def queue_name(self):
        return self.configuration.queue_name

    @cached_property
    def delete_consumed_messages(self):
        return self.configuration.delete_consumed_messages

    @cached_property
    def queue_url(self):
        return self.sqs_client.get_queue_url(QueueName=self.queue_name)["QueueUrl"]

    @cached_property
    def s3_client(self):
        return self.session.client("s3")

    @abstractmethod
    def _parse_content(self, content: bytes) -> list:
        raise NotImplementedError()

    def get_next_messages(self, **kwargs) -> list[dict]:
        response = self.sqs_client.receive_message(QueueUrl=self.queue_url, **kwargs)
        return response.get("Messages", [])

    def get_next_objects(self, messages: list) -> Generator[AWSS3Object, None, None]:
        receipts = []
        for message in messages:
            decoded_messages = []
            try:
                decoded_messages = orjson.loads(message["Body"].encode("utf-8")).get("Records", [])
            except ValueError as e:
                self.log_exception(e, message=f"Invalid JSON in message.\nInvalid message is: {message}")
            for record in decoded_messages:
                try:
                    yield AWSS3Object.from_record(self.s3_client, record)

                    if receipt := message.get("ReceiptHandle"):
                        receipts.append(receipt)
                except ValueError as e:  # pragma: no cover
                    self.log_exception(e, message="Invalid record")
        if self.delete_consumed_messages:
            entries = [{"Id": f"{index:04d}", "ReceiptHandle": receipt} for index, receipt in enumerate(receipts)]
            if entries:
                self.sqs_client.delete_message_batch(QueueUrl=self.queue_url, Entries=entries)

    def forward_next_batches(self):
        messages = self.get_next_messages()

        if len(messages) > 0:
            for next_object in self.get_next_objects(messages):
                try:
                    content = next_object.read()
                    records = self._parse_content(content)

                    if records:
                        self.log(message=f"Forwarding {len(records)} records", level="info")
                        self.push_events_to_intakes(events=records)
                    else:
                        self.log(message="No records to forward", level="info")
                except Exception as e:
                    self.log(
                        message=f"Failed to fetch content of {next_object.key}: {str(e)}",
                        level="warning",
                    )
        else:
            self.log(
                message=f"No messages to process. Wait next batch in {self.configuration.frequency}s",
                level="info",
            )
            time.sleep(self.configuration.frequency)

    def run(self):  # pragma: no cover
        self.log(message=f"Starting {self.name} Trigger", level="info")

        try:
            while True:
                self.forward_next_batches()
        finally:
            self.log(message=f"Stopping {self.name} Trigger", level="info")
