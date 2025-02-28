import time
from datetime import datetime
from functools import cached_property
from threading import Event, Lock, Thread
from typing import Any, Generator, Optional

import orjson
import requests
from requests import Response
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import VadeCloudModule
from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class FetchEventException(Exception):
    pass


class APIException(Exception):

    def __init__(self, code: int, reason: str, content: str):
        super().__init__(reason)
        self.code = code
        self.content = content


class VadeCloudConsumer(Thread):
    def __init__(
        self,
        connector: "VadeCloudLogsConnector",
        name: str,
        client: ApiClient,
        params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()

        self.connector = connector
        self.params = params or {}
        self.name = name
        self.client = client
        self._stop_event = Event()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def running(self) -> bool:
        return not self._stop_event.is_set()

    def log(self, *args: Any, **kwargs: Optional[Any]) -> None:
        self.connector.log(*args, **kwargs)

    def get_last_timestamp(self) -> int:
        now = int(time.time() * 1000)  # in milliseconds

        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            most_recent_ts_seen = int(cache.get("last_ts", 0))

        self.connector.context_lock.release()

        # if undefined, retrieve events from the last 5 minutes
        if most_recent_ts_seen is None:
            return now - 5 * 60 * 1000

        # We don't retrieve messages older than one week
        one_week_ago = now - 7 * 24 * 60 * 60 * 1000
        if most_recent_ts_seen < one_week_ago:
            most_recent_ts_seen = one_week_ago

        return most_recent_ts_seen

    def set_last_timestamp(self, last_timestamp: int) -> None:
        self.connector.context_lock.acquire()

        with self.connector.context as cache:
            cache["last_ts"] = last_timestamp

        self.connector.context_lock.release()

    def request_logs_page(self, start_date: int, period: str, page: int = 0) -> Response:
        params = {
            "userId": self.client.account_id,
            "pageSize": self.connector.configuration.chunk_size,
            "pageToGet": page,
            # "streamType": "Inbound",
            "period": period,
            "startDate": start_date,
        }
        params.update(self.params)  # override with custom stuff

        response = self.client.post(
            f"{self.connector.module.configuration.hostname}/rest/v3.0/filteringlog/getReport", json=params, timeout=60
        )

        return response

    def _handle_response_error(self, response: Response) -> None:
        if not response.ok:
            message = f"Request on Vade Cloud API to fetch `{self.name}` logs failed with status {response.status_code} - {response.reason}"

            if response.status_code == 403:
                self.log(message=message, level="critical")
            elif response.status_code in [401, 500]:
                raise APIException(response.status_code, response.reason, response.text)
            else:
                try:
                    error = response.json()
                    message = f"{message}: {error['error']}"

                except requests.exceptions.JSONDecodeError as e:  # pragma: no cover
                    self.log(message="Cannot parse not 200 response as json {0}".format(str(e)), level="debug")

                raise FetchEventException(message)

    def iterate_through_pages(self, from_timestamp: int) -> Generator[list[dict[str, Any]], None, None]:
        page_num = 0
        # long period will allow us to capture events with big time gap between them
        search_period = "DAYS_07"
        response = self.request_logs_page(start_date=from_timestamp, period=search_period, page=page_num)
        self._handle_response_error(response)

        while self.running:
            events = response.json().get("logs", [])

            if len(events) > 0:
                yield events
                page_num += 1

            else:
                return

            response = self.request_logs_page(start_date=from_timestamp, period=search_period, page=page_num)

    def fetch_events(self) -> Generator[list[dict[str, Any]], None, None]:
        most_recent_timestamp_seen = self.get_last_timestamp()

        for next_events in self.iterate_through_pages(most_recent_timestamp_seen):
            if next_events:
                # get the greater date seen in this list of events

                last_event = max(next_events, key=lambda x: int(x.get("date", 0)))
                last_event_timestamp: int | None = last_event.get("date")

                self.log(
                    message="{0}: Last event timestamp is {1} which is {2}".format(
                        self.name,
                        last_event_timestamp,
                        (
                            datetime.fromtimestamp(last_event_timestamp // 1000).isoformat()
                            if last_event_timestamp
                            else 0
                        ),
                    ),
                    level="debug",
                )

                if last_event_timestamp:  # pragma: no cover
                    event_lag = int(time.time()) - last_event_timestamp // 1000
                    EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key, type=self.name).set(
                        event_lag
                    )

                    # save the greater date ever seen
                    if last_event_timestamp > most_recent_timestamp_seen:
                        most_recent_timestamp_seen = last_event_timestamp + 1000

                # forward current events
                yield next_events

        # save the most recent date
        if most_recent_timestamp_seen > self.get_last_timestamp():
            self.set_last_timestamp(most_recent_timestamp_seen)

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"{self.name}: Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )

                INCOMING_MESSAGES.labels(intake_key=self.connector.configuration.intake_key, type=self.name).inc(
                    len(batch_of_events)
                )

                self.connector.push_events_to_intakes(events=batch_of_events)

                OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key, type=self.name).inc(
                    len(events)
                )

            else:
                self.log(
                    message="{self.name}: No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)

        FORWARD_EVENTS_DURATION.labels(intake_key=self.connector.configuration.intake_key, type=self.name).observe(
            batch_duration
        )

        self.log(
            message=f"{self.name}: Fetched and forwarded events in {batch_duration} seconds",
            level="info",
        )

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.connector.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"{self.name}: Next batch in the future. Waiting {delta_sleep} seconds",
                level="info",
            )

            time.sleep(delta_sleep)

    def handle_api_exception(self, error: APIException) -> None:
        message = f"Unexpected API error {error.code} - {str(error)} - {error.content}"
        if error.code == 401:
            message = "The VadeCloud API raised an authentication issue. Please check our credentials"
        elif error.code == 500:
            message = (
                "The VadeCloud API raised an internal error. Please contact the Vade support if the issue persists"
            )

        self.connector.log(message, level="error")
        self.connector.log(
            f"WatchGuard: Wait {self.connector.configuration.frequency}s before next attempt", level="info"
        )
        time.sleep(self.connector.configuration.frequency)

    def run(self) -> None:  # pragma: no cover
        try:
            while self.running:
                try:
                    self.next_batch()
                except APIException as error:
                    self.handle_api_exception(error)

        except Exception as error:
            self.connector.log_exception(error, message=f"{self.name}: Failed to forward events")


class VadeCloudConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 1000
    ratelimit_per_minute: int = 20


class VadeCloudLogsConnector(Connector):
    configuration: VadeCloudConnectorConfiguration
    module: VadeCloudModule

    all_params = {
        "inbound": {"streamType": "Inbound"},
        "outbound": {"streamType": "Outbound"},
    }

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()
        self.consumers: dict[str, VadeCloudConsumer] = {}

    def create_client(self) -> ApiClient:
        try:
            return ApiClient(
                hostname=self.module.configuration.hostname,
                login=self.module.configuration.login,
                password=self.module.configuration.password,
                ratelimit_per_minute=self.configuration.ratelimit_per_minute,
            )

        except requests.exceptions.HTTPError as error:
            error_response = error.response
            if error_response is None:
                raise ValueError("Response does not contain any valid data")

            http_error_code = error_response.status_code
            if http_error_code in [401, 403, 404]:
                self.log(message=f"Wrong login or password. Please check our credentials", level="critical")

            if http_error_code == 400 and error_response.json().get("error", {}).get("trKey", "") == "INVALID_USER":
                self.log(
                    message=f"Invalid account type. It must be User, not Admin. Please change it", level="critical"
                )

            raise error

        except TimeoutError as error:
            self.log(message="Failed to authorize due to timeout", level="error")

            raise error

    def start_consumers(self, client: ApiClient) -> dict[str, VadeCloudConsumer]:
        consumers = {}

        for consumer_name, params in self.all_params.items():
            self.log(message=f"Start `{consumer_name}` consumer", level="info")
            consumers[consumer_name] = VadeCloudConsumer(
                connector=self, name=consumer_name, client=client, params=params
            )
            consumers[consumer_name].start()

        return consumers

    def supervise_consumers(self, consumers: dict[str, VadeCloudConsumer], client: ApiClient) -> None:
        for consumer_name, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restart consuming logs of `{consumer_name}` emails", level="info")

                consumers[consumer_name] = VadeCloudConsumer(
                    connector=self,
                    name=consumer_name,
                    client=client,
                    params=self.all_params.get(consumer_name),
                )
                consumers[consumer_name].start()

    def stop_consumers(self, consumers: dict[str, VadeCloudConsumer]) -> None:
        for consumer_name, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stop consuming logs of `{consumer_name}` emails", level="info")
                consumer.stop()

    def run(self) -> None:  # pragma: no cover
        client = self.create_client()
        consumers = self.start_consumers(client=client)

        while self.running:
            self.supervise_consumers(consumers, client=client)
            time.sleep(5)

        self.stop_consumers(consumers)
