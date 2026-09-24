import os
import time
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

import orjson
import tenacity
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.helpers.timestepper import TimeStepper
from sekoia_automation.storage import PersistentJSON
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

from . import VaronisModule
from .client import ApiClient, VaronisApiError
from .client.auth import VaronisAuthenticationError
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class VaronisSaaSAlertsConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    timedelta: int = 5
    start_time: int = 1


class VaronisJobError(Exception):
    pass


class VaronisSaaSAlertsConnector(Connector):
    module: VaronisModule
    configuration: VaronisSaaSAlertsConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self.data_path)
        self.cache_size = int(os.getenv("EVENTS_CACHE_SIZE", 2000))
        self.events_cache: Cache[str, bool] = self.load_events_cache()
        self.max_job_timeout = int(os.getenv("MAX_JOB_TIMEOUT", 300))

    @cached_property
    def stepper(self) -> TimeStepper:
        with self.context as cache:
            most_recent_date_requested_str = cache.get("most_recent_date_requested")

        if most_recent_date_requested_str is None:
            return TimeStepper.create(
                trigger=self,
                frequency=self.configuration.frequency,
                timedelta=self.configuration.timedelta,
                start_time=self.configuration.start_time,
                metric=EVENTS_LAG,
            )

        # parse the most recent requested date
        most_recent_date_requested = isoparse(most_recent_date_requested_str)

        now = datetime.now(UTC)
        one_week_ago = now - timedelta(days=7)
        if most_recent_date_requested < one_week_ago:
            most_recent_date_requested = one_week_ago

        return TimeStepper.create_from_time(
            trigger=self,
            start=most_recent_date_requested,
            frequency=self.configuration.frequency,
            timedelta=self.configuration.timedelta,
            metric=EVENTS_LAG,
        )

    def load_events_cache(self) -> Cache[str, bool]:
        """
        Load the events cache.
        """
        cache: Cache[str, bool] = LRUCache(maxsize=self.cache_size)

        with self.context as context:
            # load the cache from the context
            events_cache = context.get("events_cache", [])

        for uuid in events_cache:
            cache[uuid] = True

        return cache

    def save_events_cache(self) -> None:
        """
        Save the events cache.
        """
        with self.context as context:
            # save the events cache to the context
            context["events_cache"] = list(self.events_cache.keys())

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            base_url=self.module.configuration.base_url,
            api_key=self.module.configuration.api_key,
        )

    def is_processed(self, event: dict[str, Any]) -> bool:
        return event["id"] in self.events_cache

    def mark_processed(self, event: dict[str, Any]) -> None:
        self.events_cache[event["id"]] = True

    @tenacity.retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=0.5, max=5),
        retry=retry_if_exception_type(exception_types=VaronisJobError),
        reraise=True,
    )
    def fetch_events(self, from_date: datetime, to_date: datetime) -> list[dict[str, Any]]:
        from_str = from_date.strftime(RFC3339_STRICT_FORMAT)
        to_str = to_date.strftime(RFC3339_STRICT_FORMAT)
        self.log(message=f"Fetching events from {from_str} to {to_str}", level="info")

        # create a job
        response = self.client.alerts_async(from_date=from_str, to_date=to_str)
        job_id = response["data"]["alertsAsync"]["jobId"]

        start_time = time.monotonic()
        while self.running:
            response = self.client.alerts_query_job(job_id=job_id)
            raw = response["data"]["alertsQueryJob"]

            status = raw["jobStatus"]
            if status == "COMPLETED":
                events = raw["results"]
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events))

                return events

            elif status in ("CANCELED", "FAILED"):
                raise VaronisJobError(f"Job {job_id} is {status}")

            if time.monotonic() - start_time > self.max_job_timeout:
                raise VaronisJobError(
                    f"Job {job_id} did not complete within {self.max_job_timeout} seconds (last status: {status})"
                )

            # otherwise - its pending, and we should wait a bit and ask again
            time.sleep(1)

        return []

    def run(self) -> None:  # pragma: no cover
        self.log(message="Varonis SaaS Alerts connector has started.", level="info")

        for start, end in self.stepper.ranges():
            # check if the trigger should stop
            if not self.running:
                break

            try:
                duration_start = time.time()
                events = self.fetch_events(start, end)

                batch_of_events = [
                    orjson.dumps(event).decode("utf-8") for event in events if not self.is_processed(event)
                ]

                if len(batch_of_events) > 0:
                    self.log(
                        message=f"Forwarding {len(batch_of_events)} events",
                        level="info",
                    )
                    self.push_events_to_intakes(events=batch_of_events)

                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))

                    # mark sent events as processed
                    for event in events:
                        self.mark_processed(event)
                    self.save_events_cache()

                else:
                    self.log(message="No events to forward", level="info")

                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                    time.time() - duration_start
                )

            except VaronisApiError as e:
                errors = e.js.get("errors", [])
                for error in errors:
                    extensions = error.get("extensions")
                    if extensions:
                        error_code = extensions.get("errorCode")
                        error_message = extensions.get("errorMessage")
                        error_detail = extensions.get("errorDetail")
                        self.log(
                            f"{error_code}: {error_message}: {error_detail}",
                            level="error",
                        )

                    else:
                        error_message = error.get("message")
                        self.log(error_message, level="error")

                raise

            except VaronisAuthenticationError as e:
                self.log(str(e), level="critical")
                raise

            except Exception as ex:
                self.log_exception(ex, message="Failed to fetch events.")
                raise ex

            finally:
                # save in context the most recent date seen
                with self.context as cache:
                    cache["most_recent_date_requested"] = end.isoformat()
