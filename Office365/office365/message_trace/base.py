import time
from abc import abstractmethod
from datetime import UTC, datetime, timedelta
from functools import cached_property
from json.decoder import JSONDecodeError
from threading import Event

import orjson
from dateutil.parser import isoparse
from requests import Response
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from tenacity import Retrying, stop_after_attempt, wait_exponential

from office365.metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

from .timestepper import TimeStepper


class O365BaseConfig(DefaultConnectorConfiguration):
    frequency: int = 60
    timedelta: int = 1
    start_time: int = 1


class Office365MessageTraceBaseTrigger(Connector):
    """
    This base trigger to fetch events from Office 365 MessageTrace
    """

    configuration: O365BaseConfig

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = {"Accept": "application/json"}
        self.messagetrace_api_url: str = (
            "https://reports.office365.com/ecp/reportingwebservice/reporting.svc/MessageTrace"
        )
        self._stop_event = Event()
        self.context = PersistentJSON("context.json", self._data_path)

    def stop(self, *args, **kwargs):
        self.log(message="Stopping Office365 MessageTrace trigger", level="info")
        super().stop(*args, **kwargs)

    @cached_property
    def stepper(self):
        with self.context as cache:
            most_recent_date_requested_str = cache.get("most_recent_date_requested")

            if most_recent_date_requested_str is None:
                return TimeStepper.create(
                    self,
                    self.configuration.frequency,
                    self.configuration.timedelta,
                    self.configuration.start_time,
                )

            # parse the most recent requested date
            most_recent_date_requested = isoparse(most_recent_date_requested_str)

            # We don't retrieve messages older than 30 days
            # see https://learn.microsoft.com/en-us/previous-versions/office/developer/o365-enterprise-developers/↵
            # jj984335(v=office.15)?redirectedfrom=MSDN#data-granularity-persistence-and-availability
            now = datetime.now(UTC)
            one_month_ago = now - timedelta(days=30)
            if most_recent_date_requested < one_month_ago:
                most_recent_date_requested = one_month_ago

            return TimeStepper.create_from_time(
                self,
                most_recent_date_requested,
                self.configuration.frequency,
                self.configuration.timedelta,
            )

    @staticmethod
    def serialize_json(events) -> list[str]:
        return [orjson.dumps(event).decode("utf-8") for event in events]

    def _retry(self):
        return Retrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )

    @abstractmethod
    def query_api(self, start: datetime, end: datetime) -> list[str]:
        raise NotImplementedError

    def manage_response(self, response: Response) -> list[str]:
        if not response.ok:
            self.log(
                message=(
                    f"Request on MessageTrace API to fetch {response.url} "
                    f"failed with status {response.status_code} - {response.text}"
                ),
                level="error",
            )
            return []

        try:
            response_json = response.json()
            messages: list[dict] = response_json.get("d", {}).get("results", None)

        except JSONDecodeError as err:
            self.log_exception(
                err,
                message=(
                    f"Request on MessageTrace API to fetch {response.url} "
                    f"failed, invalid JSON payload was returned."
                ),
            )
            return []

        except Exception as e:
            self.log_exception(
                e,
                message="Office365 MessageTrace Trigger encountered an error",
            )
            raise e

        json_messages: list[str] = self.serialize_json(messages)
        return json_messages

    def run(self):  # pragma: no cover
        self.log(message="Office365 MessageTrace Trigger has started.", level="info")

        for start, end in self.stepper.ranges():
            # check if the trigger should stop
            if self._stop_event.is_set():
                break

            try:
                duration_start = time.time()
                messages: list[str] = self.query_api(start, end)
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))

                if len(messages) > 0:
                    self.log(message=f"Forwarding {len(messages)} records", level="info")
                    self.push_events_to_intakes(events=messages)
                else:
                    self.log(message="No records to forward", level="info")

                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                    time.time() - duration_start
                )
            except Exception as ex:
                self.log_exception(ex, message="Failed to fetch events.")
                raise ex
            finally:
                # save in context the most recent date seen
                with self.context as cache:
                    cache["most_recent_date_requested"] = end.isoformat()
