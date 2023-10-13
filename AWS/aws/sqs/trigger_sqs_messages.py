import time
from functools import cached_property

import orjson
from sekoia_automation.connector import DefaultConnectorConfiguration

from aws.base import AWSConnector


class AWSSQSConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 10000
    delete_consumed_messages: bool = False
    queue_name: str


class AWSSQSMessagesTrigger(AWSConnector):
    name = "AWS SQS Messages"
    configuration: AWSSQSConfiguration

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

    def forward_next_batches(self, **kwargs):
        response = self.sqs_client.receive_message(QueueUrl=self.queue_url, **kwargs)
        messages = response.get("Messages", [])

        if len(messages) > 0:
            receipts = []
            records = []
            for message in messages:
                decoded_messages = []
                try:
                    decoded_messages = orjson.loads(message["Body"].encode("utf-8")).get("Records", [])
                except ValueError as e:
                    self.log_exception(e, message=f"Invalid JSON in message.\nInvalid message is: {message}")
                for record in decoded_messages:
                    try:
                        records.append(record)

                        if receipt := message.get("ReceiptHandle"):
                            receipts.append(receipt)
                    except ValueError as e:  # pragma: no cover
                        self.log_exception(e, message="Invalid record")
            if records:
                self.log(message=f"Forwarding {len(records)} messages", level="info")
                self.push_events_to_intakes(events=records)
            else:
                self.log(message="No messages to forward", level="info")

            if self.delete_consumed_messages:
                entries = [{"Id": f"{index:04d}", "ReceiptHandle": receipt} for index, receipt in enumerate(receipts)]
                if entries:
                    self.sqs_client.delete_message_batch(QueueUrl=self.queue_url, Entries=entries)
        else:  # pragma: no cover
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
