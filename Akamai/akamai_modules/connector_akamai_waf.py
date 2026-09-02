import base64
import os
import re
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Generator

import orjson
import requests
from cachetools import Cache, LRUCache
from pydantic.v1 import Field
from sekoia_automation.checkpoint import CheckpointTimestamp, TimeUnit
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from . import AkamaiModule
from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class AkamaiWAFLogsConnectorConfiguration(DefaultConnectorConfiguration):
    config_id: str = Field(..., description="The Web Security Configuration ID")
    frequency: int = Field(60, description="Batch frequency in seconds", ge=1)


class AkamaiWAFLogsConnector(Connector):
    module: AkamaiModule
    configuration: AkamaiWAFLogsConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointTimestamp(
            path=self._data_path,
            time_unit=TimeUnit.SECOND,
            start_at=timedelta(hours=1),
            ignore_older_than=timedelta(hours=12),
        )
        self.from_timestamp: int = self.cursor.offset

        # This cache should be big enough to cover all events within 1 second.
        self.cache_size = 10_000
        self.events_cache: Cache = self.load_events_cache()

        self.page_size = max(
            1000, min(60_000, int(os.environ.get("AKAMAI_PAGE_SIZE", 60_000)))
        )  # default 1000, maximum 60000
        self.chunk_size = max(
            1, min(1000, int(os.environ.get("AKAMAI_CHUNK_SIZE", 1_000)))
        )  # number of events to accumulate before yielding to limit memory usage

    def load_events_cache(self) -> Cache:
        result: LRUCache = LRUCache(maxsize=self.cache_size)

        with self.cursor._context as cache:
            events_ids = cache.get("events_cache", [])

        for event_id in events_ids:
            result[event_id] = True

        return result

    def save_events_cache(self) -> None:
        with self.cursor._context as cache:
            cache["events_cache"] = list(self.events_cache.keys())

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            client_token=self.module.configuration.client_token,
            client_secret=self.module.configuration.client_secret,
            access_token=self.module.configuration.access_token,
        )

    @staticmethod
    def extract_attack_data(event: dict[str, Any]) -> dict[str, Any]:
        attack_section = event["attackData"]
        rules_array: list[dict[str, Any]] = []

        new_attack_section = {}
        for member in attack_section:
            if member[0:4] != "rule":
                new_attack_section[member] = attack_section[member]
                continue

            # Alternate field name converted from plural:
            member_as_singular = re.sub("s$", "", member)
            url_decoded = urllib.parse.unquote(attack_section[member])
            member_array = [item for item in url_decoded.split(";")]
            if not len(rules_array):
                for i in range(len(member_array)):
                    rules_array.append({})
            i = 0
            for item in member_array:
                rules_array[i][member_as_singular] = base64.b64decode(item).decode("utf-8", errors="backslashreplace")
                i += 1

            new_attack_section["rules"] = rules_array

        return new_attack_section

    @staticmethod
    def _extract_headers_with_diagnostics(headers: Any) -> tuple[dict[str, Any], dict[str, int]]:
        result = {}
        malformed_line_reasons: Counter[str] = Counter()

        if not isinstance(headers, str):
            malformed_line_reasons["invalid_type"] += 1
            return result, dict(malformed_line_reasons)

        for item in urllib.parse.unquote(headers).splitlines():
            item = item.strip()
            if not item:
                continue

            if ":" not in item:
                malformed_line_reasons["missing_separator"] += 1
                continue

            header_key, header_value = map(str.strip, item.split(":", maxsplit=1))
            if not header_key:
                malformed_line_reasons["empty_key"] += 1
                continue

            result[header_key] = header_value

        return result, dict(malformed_line_reasons)

    @staticmethod
    def extract_headers(headers: str) -> dict[str, Any]:
        result, _ = AkamaiWAFLogsConnector._extract_headers_with_diagnostics(headers)
        return result

    def process_event(self, event: dict[str, Any]) -> None:
        # Processing `attackData` section
        new_attack_section = self.extract_attack_data(event)

        # Processing `httpMessage` section
        request_headers = None
        request_malformed = {}
        if "requestHeaders" in event.get("httpMessage", {}):
            request_headers, request_malformed = self._extract_headers_with_diagnostics(
                event.get("httpMessage", {}).get("requestHeaders")
            )

        response_headers = None
        response_malformed = {}
        if "responseHeaders" in event.get("httpMessage", {}):
            response_headers, response_malformed = self._extract_headers_with_diagnostics(
                event.get("httpMessage", {}).get("responseHeaders")
            )

        event["attackData"] = new_attack_section
        if "requestHeaders" in event.get("httpMessage", {}):
            event["httpMessage"]["requestHeaders"] = request_headers

        if "responseHeaders" in event.get("httpMessage", {}):
            event["httpMessage"]["responseHeaders"] = response_headers

        ignored_request_lines = sum(request_malformed.values())
        ignored_response_lines = sum(response_malformed.values())
        if ignored_request_lines or ignored_response_lines:
            self.log(
                message=(
                    "Ignored malformed HTTP header lines while processing Akamai event "
                    f"request_header_lines_ignored={ignored_request_lines} "
                    f"response_header_lines_ignored={ignored_response_lines} "
                    f"request_malformed_reasons={request_malformed} "
                    f"response_malformed_reasons={response_malformed}"
                ),
                level="warning",
            )

    def __fetch_next_events(self, from_date: int) -> Generator[list, None, None]:
        url = f"{self.module.configuration.base_url}/siem/v1/configs/{self.configuration.config_id}"
        response = self.client.get(
            url=url, params={"from": from_date, "limit": self.page_size}, timeout=60, stream=True
        )

        while self.running:
            self.__handle_response_error(response)

            chunk: list = []
            offset = None
            events_in_page = 0

            for line in response.iter_lines():
                if line:
                    item: dict = orjson.loads(line)
                    if item.get("type") == "akamai_siem":
                        self.process_event(item)
                        chunk.append(item)
                        events_in_page += 1

                        if len(chunk) >= self.chunk_size:
                            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(chunk))
                            yield chunk
                            chunk = []

                    else:
                        offset = item["offset"]
                        # response context - last JSON line
                        if events_in_page > 0:
                            # Yield remaining events that didn't fill a full chunk
                            if chunk:
                                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(chunk))
                                yield chunk
                                chunk = []

                        else:
                            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
                            return

            if offset is None:
                if chunk:
                    INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(chunk))
                    yield chunk
                return

            response = self.client.get(
                url=url, params={"offset": offset, "limit": self.page_size}, timeout=60, stream=True
            )

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen: int = self.from_timestamp

        for next_events in self.__fetch_next_events(most_recent_date_seen):
            if next_events:
                latest_event = max(next_events, key=lambda x: int(x["httpMessage"]["start"]))
                latest_timestamp = int(latest_event["httpMessage"]["start"])

                if latest_timestamp > most_recent_date_seen:
                    most_recent_date_seen = latest_timestamp

                # forward current events
                yield next_events

        # save the most recent date
        if most_recent_date_seen > self.from_timestamp:
            self.from_timestamp = most_recent_date_seen
            self.cursor.offset = most_recent_date_seen

            delta_time = datetime.now(timezone.utc).timestamp() - most_recent_date_seen
            current_lag = int(delta_time)
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

    def __handle_response_error(self, response: requests.Response):
        if not response.ok:
            message = (
                f"Request on Akamai API to fetch events failed with status {response.status_code} - {response.reason}"
            )
            self.log(
                message=message,
                level="error",
            )

            try:
                raw = response.json()
                self.log(
                    message=(
                        f"{message} "
                        f"client_ip={raw.get('clientIp')} "
                        f"detail={raw.get('detail')} "
                        f"instance={raw.get('instance')} "
                        f"method={raw.get('method')} "
                        f"request_id={raw.get('requestId')} "
                        f"request_time={raw.get('requestTime')} "
                        f"server_ip={raw.get('serverIp')} "
                        f"title={raw.get('title')} "
                        f"type={raw.get('type')}"
                    ),
                    level="error",
                )

            except Exception:
                pass

            response.raise_for_status()

    def filter_processed_events(self, events: list[dict]) -> Generator[dict, None, None]:
        for event in events:
            event_id = event["httpMessage"]["requestId"]
            if event_id in self.events_cache:
                continue

            self.events_cache[event_id] = True
            yield event

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in self.filter_processed_events(events)]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))

                self.push_events_to_intakes(events=batch_of_events)
                self.save_events_cache()

            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(f"Fetched and forwarded events in {batch_duration} seconds", level="debug")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(f"Next batch in the future. Waiting {delta_sleep} seconds", level="debug")
            time.sleep(delta_sleep)

    def run(self):  # pragma: no cover
        self.log(message="Start fetching Akamai WAF system logs", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
