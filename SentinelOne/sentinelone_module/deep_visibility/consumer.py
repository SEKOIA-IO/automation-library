import signal
import time
import zlib

import certifi
import orjson
from confluent_kafka import Consumer, TopicPartition
from google.protobuf.json_format import MessageToDict
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from sentinelone_module.deep_visibility import export_pb2


class DeepVisibilityTriggerSetting(DefaultConnectorConfiguration):
    bootstrap_servers: str
    username: str
    password: str
    group_id: str
    topic: str


class DeepVisibilityTrigger(Connector):
    _consumer: Consumer
    _should_stop: bool
    configuration: DeepVisibilityTriggerSetting

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        self._should_stop = False

    def _create_kafka_consumer(self) -> None:
        self._consumer = Consumer(
            {
                "bootstrap.servers": self.configuration.bootstrap_servers,
                "security.protocol": "SASL_SSL",
                "sasl.mechanisms": "SCRAM-SHA-512",
                "sasl.username": self.configuration.username,
                "sasl.password": self.configuration.password,
                "ssl.ca.location": certifi.where(),
                "group.id": self.configuration.group_id,
                # Disable TLS certificate hostname verification that
                # is known to break authentication to SentinelOne
                # Kafka brokers since `librdkafka2`.
                #
                # https://github.com/confluentinc/librdkafka/releases/tag/v2.0.0
                "ssl.endpoint.identification.algorithm": "none",
            }
        )
        self._consumer.subscribe([self.configuration.topic], on_assign=self._on_assign, on_revoke=self._on_revoke)
        assigned_partitions = ", ".join([str(assignment.partition) for assignment in self._consumer.assignment()])
        self.log(
            message=f"DeepVisibility consumer initialized. Assigned Kafka partitions: {assigned_partitions}",
            level="info",
        )

    def _on_assign(self, _: Consumer, partitions: list[TopicPartition]) -> None:
        partitions_str: str = ", ".join([str(partition.partition) for partition in partitions])
        self.log(message=f"Kafka consumer was assigned new partitions: {partitions_str}", level="info")

    def _on_revoke(self, _: Consumer, partitions: list[TopicPartition]) -> None:
        partitions_str: str = ", ".join([str(partition.partition) for partition in partitions])
        self.log(message=f"Kafka consumer was asked to revoke partitions: {partitions_str}", level="info")

    def run(self) -> None:
        self.log(message="SentineOne DeepVisibility Trigger has started.", level="info")

        processed_events = 0
        last_log_at: float = 0.0

        self._create_kafka_consumer()
        while not self._should_stop:
            processed_events += self._handle_kafka_message(last_log_at)

        self._consumer.commit()
        self._consumer.close()

        self.log(message="Trigger has now completed its work.", level="info")

    def _handle_kafka_message(self, last_log_at: float) -> int:
        message = self._consumer.poll(0)

        if message is None:
            return 0

        if message.error():
            self._logger.error(message.error())
            return 0

        else:
            try:
                messages = self._process_events(message.value())
                self.push_events_to_intakes(events=messages)
            except Exception as exp:
                self.log_exception(exp, message="Failed to fetch events.")
                raise exp

        if time.time() - last_log_at >= 10 * 60:
            self._log_current_lag()
            last_log_at = time.time()

        return 1

    def _log_current_lag(self) -> None:
        """Log the currently observed lag for the configured Kafka
        consumer.

        """
        lag: list[str] = []

        last_offsets = self._consumer.committed(self._consumer.assignment())
        for last_offset in last_offsets:
            _, high_offset = self._consumer.get_watermark_offsets(last_offset)
            observed_lag = high_offset - 1 - last_offset.offset
            lag.append(f"partition{last_offset.partition}={observed_lag}")

        lag_str = ";".join(lag)
        self.log(message=f"Lag for current Kafka partitions: {lag_str}", level="info")

    def stop(self, _, __) -> None:
        self.log(message="Asking trigger to stop", level="info")
        self._should_stop = True

    def _process_events(self, compressed_event: bytes) -> list[str]:
        """
        Process the given event
        """
        raw_event = zlib.decompress(compressed_event)
        packet = export_pb2.Packet()  # type: ignore
        packet.ParseFromString(raw_event)
        meta_dict = MessageToDict(packet.meta)

        events_to_push: list[str] = []

        for evt in packet.events:
            event_dict = MessageToDict(evt)

            event_to_push: dict = {
                "meta": meta_dict,
            }
            # The event dict has only two keys:
            #   * timestamp: the timestamp value
            #   * {event_type}: The real event dict
            event_to_push["timestamp"] = event_dict.pop("timestamp", None)
            # We now have only one key in the dict, the event one.
            event_type, event = next(iter(event_dict.items()))
            event_to_push["event_type"] = event_type
            # Add the real event details at the root of the event that will be pushed
            event_to_push.update(event)

            event_str = orjson.dumps(event_to_push).decode("utf-8")
            events_to_push.append(event_str)

        return events_to_push
