import logging
import os
from datetime import datetime, timezone
from functools import cached_property

import orjson
from confluent_kafka import Producer


class KafkaForwarder:
    @cached_property
    def kafka_bootstrap_servers(self) -> str | None:
        return os.environ.get("KAFKA_PRODUCER_BOOTSTRAP_SERVERS")

    @cached_property
    def kafka_topic(self) -> str | None:
        return os.environ.get("KAFKA_TOPIC")

    @cached_property
    def kafka_producer(self) -> Producer | None:  # pragma: no cover
        if self.kafka_bootstrap_servers is None or self.kafka_topic is None:
            logging.info("No configuration for kafka producer")
            return None

        logging.info(f"Create kafka producer for {self.kafka_bootstrap_servers}/{self.kafka_topic}")
        return Producer(
            {"bootstrap.servers": self.kafka_bootstrap_servers, "linger.ms": 10, "compression.codec": "gzip"}
        )

    def generate_message(self, timestamp: str, message: str):
        return orjson.dumps(
            {
                "@timestamp": timestamp,
                "message": message,
            }
        )

    def produce(self, records: list[str]):
        if self.kafka_producer:
            timestamp = datetime.now(timezone.utc).isoformat()
            try:
                self.kafka_producer.poll(0)

                for record in records:
                    self.kafka_producer.produce(self.kafka_topic, self.generate_message(timestamp, record))
                self.kafka_producer.flush()
            except Exception:
                logging.exception("Failed to forward events to kafka")
