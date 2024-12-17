import time
from functools import cached_property
from json.decoder import JSONDecodeError
from threading import Event, Thread

import orjson
from netskope_api.iterator.const import Const
from netskope_api.iterator.netskope_iterator import NetskopeIterator
from pydantic import Field
from requests.exceptions import ConnectionError
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.exceptions import ModuleConfigurationError

from netskope_modules import NetskopeModule
from netskope_modules.constants import MESSAGE_CANNOT_CONSUME_SERVICE
from netskope_modules.helpers import get_index_name, get_iterator_name, get_tenant_hostname
from netskope_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from netskope_modules.types import NetskopeAlertType, NetskopeEventType


class NetskopeEventConnectorConfiguration(DefaultConnectorConfiguration):
    api_token: str = Field(..., description="The API token")
    consumer_group: str | None = Field(None, description="A unique name to track events consumption")


class NetskopeEventConsumer(Thread):
    def __init__(self, connector: "NetskopeEventConnector", name: str, iterator: NetskopeIterator):
        super().__init__()
        self.connector = connector
        self.name = name
        self.iterator = iterator
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()

        # Fetch next events
        try:
            response = self.iterator.next()
        except ConnectionError as error:
            if "connection aborted" in str(error).lower():
                return

            raise error

        if response.status_code == 204:
            self.connector.log(message=f"No events to forward for {self.name}", level="info")
        if response.status_code == 403:
            try:
                message = response.json().get("message")
                if message == MESSAGE_CANNOT_CONSUME_SERVICE:
                    self.connector.log(
                        message=f"Cannot consume the service {self.name}. The consumer will be stopped.",
                        level="warning",
                    )
                    self.stop()
                    return
                else:
                    self.connector.log(
                        message=f"Cannot consume the service {self.name}. Error={message}",
                        level="error",
                    )
            except JSONDecodeError:
                self.connector.log(
                    message=f"Cannot consume the service {self.name}. Error={response.text}",
                    level="error",
                )
        elif response.status_code > 299:
            self.connector.log(
                message=f"Failed to fetch events for {self.name}: {response.status_code} {response.text}",
                level="error",
            )

        content = response.json() if response.status_code == 200 else {}

        # Serialize events and extract the most recent timestamp
        batch_of_events = []
        most_recent_timestamp = 0
        for event in content.get("result", []):
            batch_of_events.append(orjson.dumps(event).decode("utf-8"))
            if event.get("timestamp", 0) > most_recent_timestamp:
                most_recent_timestamp = event["timestamp"]
        OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key, type=self.name).inc(
            len(batch_of_events)
        )

        if len(batch_of_events) > 0:
            self.connector.push_events_to_intakes(events=batch_of_events)

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.connector.log(
            message=f"Fetch and forward {len(batch_of_events)} events in {batch_duration} seconds",
            level="info",
        )
        FORWARD_EVENTS_DURATION.labels(intake_key=self.connector.configuration.intake_key, type=self.name).observe(
            batch_end_time
        )

        # compute the lag
        current_lag: int = 0
        if most_recent_timestamp > 0:
            now = time.time()
            current_lag = int(now - most_recent_timestamp)

        # report the lag
        EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key, type=self.name).set(current_lag)

        # get the sleeping time from the response. Otherwise, compute the remaining sleeping time.
        delta_sleep = content.get("wait_time", 30 - batch_duration)
        # If greater than 0, sleep
        if delta_sleep > 0:
            self.connector.log(
                message=f"Next batch in the future. Waiting {delta_sleep} seconds",
                level="info",
            )
            time.sleep(delta_sleep)

    def run(self) -> None:
        try:
            while self.running:
                self.next_batch()
        except Exception as error:
            self.connector.log_exception(error, message=f"Failed to forward events for {self.name}")


class NetskopeEventConnector(Connector):
    """
    This connector fetches events from Netskope API
    """

    module: NetskopeModule
    configuration: NetskopeEventConnectorConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @cached_property
    def tenant_hostname(self):
        return get_tenant_hostname(self.module.configuration.base_url)

    @cached_property
    def _user_agent(self):
        return "sekoiaio-connector/{}-{}".format(
            self.module.manifest.get("slug"),
            self.module.manifest.get("version"),
        )

    @cached_property
    def dataexports(self) -> list[tuple[NetskopeEventType, NetskopeAlertType | None]]:
        return [
            (NetskopeEventType.PAGE, None),
            (NetskopeEventType.APPLICATION, None),
            (NetskopeEventType.INCIDENT, None),
            (NetskopeEventType.AUDIT, None),
            (NetskopeEventType.INFRASTRUCTURE, None),
            (NetskopeEventType.NETWORK, None),
            (NetskopeEventType.ALERT, NetskopeAlertType.DLP),
            (NetskopeEventType.ALERT, NetskopeAlertType.WATCHLIST),
            (NetskopeEventType.ALERT, NetskopeAlertType.CTEP),
            (NetskopeEventType.ALERT, NetskopeAlertType.COMPROMISEDCREDENTIAL),
            (NetskopeEventType.ALERT, NetskopeAlertType.MALSITE),
            (NetskopeEventType.ALERT, NetskopeAlertType.MALWARE),
            (NetskopeEventType.ALERT, NetskopeAlertType.POLICY),
            (NetskopeEventType.ALERT, NetskopeAlertType.REMEDIATION),
            (NetskopeEventType.ALERT, NetskopeAlertType.QUARANTINE),
            (NetskopeEventType.ALERT, NetskopeAlertType.SECURITYASSESSMENT),
            (NetskopeEventType.ALERT, NetskopeAlertType.UBA),
        ]

    @cached_property
    def configuration_uuid(self) -> str:
        if self.module.connector_configuration_uuid is not None:
            return self.module.connector_configuration_uuid

        return self.module.trigger_configuration_uuid

    def get_index_name(self, event_type: NetskopeEventType, alert_type: NetskopeAlertType | None) -> str:
        """
        return a index name for the iterator

        :param NetskopeEventType event_type: the type of the event
        :param NetskopeAlertType or None alert_type: the type of alert
        """
        # if a global consumer group is defined, return it
        if self.configuration.consumer_group and len(self.configuration.consumer_group) > 0:
            return self.configuration.consumer_group

        return get_index_name(self.configuration_uuid, event_type, alert_type)

    def create_iterator(self, event_type: NetskopeEventType, alert_type: NetskopeAlertType | None) -> NetskopeIterator:
        params: dict[str, str] = {
            Const.NSKP_TOKEN: self.configuration.api_token,
            Const.NSKP_TENANT_HOSTNAME: self.tenant_hostname,
            Const.NSKP_EVENT_TYPE: event_type.value,
            Const.NSKP_ITERATOR_NAME: self.get_index_name(event_type, alert_type),
            Const.NSKP_USER_AGENT: self._user_agent,
        }

        if event_type == NetskopeEventType.ALERT:
            if alert_type is None:
                raise ValueError("alert_type cannot be null when event_type set to 'alert'")

            params[Const.NSKP_ALERT_TYPE] = alert_type.value

        return NetskopeIterator(params)

    def create_iterators(
        self, dataexports: list[tuple[NetskopeEventType, NetskopeAlertType | None]]
    ) -> dict[str, NetskopeIterator]:
        """
        Create iterators from the list of dataexports

        :param list dataexports: The list of dataexport
        :rtype: dict[str, NetskopeIterator]
        :return: The list of iterators as dict
        """
        iterators: dict[str, NetskopeIterator] = {}

        # for each data export,
        for event_type, alert_type in dataexports:
            # compute the name
            name = get_iterator_name(event_type, alert_type)

            # generate and save the iterator
            iterators[name] = self.create_iterator(event_type, alert_type)

        return iterators

    def start_consumers(self, iterators: dict[str, NetskopeIterator]) -> dict[str, NetskopeEventConsumer]:
        """
        Start the consumers from the list of iterators

        :param dict iterators: The list of iterators
        :rtype: dict[str, NetskopeDataConsumer]
        :return: The list of consumers as dict
        """
        consumers: dict[str, NetskopeEventConsumer] = dict()

        # for each iterator
        for name, iterator in iterators.items():
            self.log(message=f"Start {name} consumer", level="info")

            # create the consumer
            consumers[name] = NetskopeEventConsumer(self, name, iterator)
            consumers[name].start()

        return consumers

    def supervise_consumers(
        self,
        consumers: dict[str, NetskopeEventConsumer],
        iterators: dict[str, NetskopeIterator],
    ):
        """
        Check the consumers and restart the dead ones

        :param dict consumers: The list of consumers
        :param dict iterators: The list of iterators
        """

        # for each iterator
        for name, iterator in iterators.items():
            # get the consumer
            consumer = consumers.get(name)

            # if missing or not alive
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restart {name} consumer", level="info")

                # (re-)create the consumer
                consumers[name] = NetskopeEventConsumer(self, name, iterator)
                consumers[name].start()

    def stop_consumers(
        self,
        consumers: dict[str, NetskopeEventConsumer],
        iterators: dict[str, NetskopeIterator],
    ):
        """
        Stop the consumers from the list of iterators

        :param dict consumers: The list of consumers
        :param dict iterators: The list of iterators
        """
        # for each iterator
        for name in iterators.keys():
            # get the consumer
            consumer = consumers.get(name)

            # if the consumer is running
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stop {name} consumer", level="info")
                consumers[name].stop()

    def run(self):
        # raise a configuration error if the base_url is not defined
        if self.module.configuration.base_url is None:
            raise ModuleConfigurationError("The base url is undefined. Please set the url of the netskope api")

        try:
            # create iterators from data exports
            iterators = self.create_iterators(self.dataexports)
            # start consumers
            consumers = self.start_consumers(iterators)

            # while the connector is running
            while self.running:
                # supervise consumers
                self.supervise_consumers(consumers, iterators)

                # Wait 5 seconds for the next supervision
                time.sleep(5)

            self.stop_consumers(consumers, iterators)
        except Exception as error:
            self.log_exception(
                error,
                message=f"Failed to forward events from {self.module.configuration.base_url}",
            )
