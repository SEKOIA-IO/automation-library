import datetime as date_time
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

import orjson
from azure.core.exceptions import AzureError, DeserializationError
from azure.core.paging import ItemPaged
from azure.identity import ClientSecretCredential
from azure.mgmt.securityinsight import SecurityInsights
from azure.mgmt.securityinsight.models import Incident, IncidentAdditionalData, IncidentLabel, IncidentOwnerInfo
from cachetools import LRUCache
from requests.exceptions import HTTPError
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, EventType
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE
from sekoia_automation.storage import PersistentJSON
from urllib3.exceptions import HTTPError as BaseHTTPError

from microsoft_sentinel import (
    MicrosoftSentinelConnectorConfiguration,
    MicrosoftSentinelModule,
    MicrosoftSentinelResponseModel,
)
from microsoft_sentinel.errors import IncidentsForwardError
from microsoft_sentinel.metrics import (
    ENTITIES_FETCH_ERRORS,
    EVENTS_LAG,
    FORWARD_EVENTS_DURATION,
    INCOMING_EVENTS,
    OUTCOMING_EVENTS,
)
from microsoft_sentinel.utils import additional_data_to_dict, labels_data_to_dict, owner_data_to_dict

MAX_BATCH_SIZE = 1000
# incidents are queried from `checkpoint - LOOKBACK` to collect the ones written late, with a creation
# date older than the checkpoint
LOOKBACK = timedelta(minutes=5)
# hard cap of the incidents remembered (and persisted) to avoid forwarding the same incident twice
DEDUP_CACHE_SIZE = 10_000
# incidents forwarded within the lookback window, persisted to survive restarts
DEDUP_KEYS_FILE = "incidents_dedup.json"
# the creation date never changes: paging on it cannot skip an incident modified during the poll
INCIDENTS_ORDER_BY = "properties/createdTimeUtc asc"
# maximum wait, in seconds, between two polls after consecutive failures
MAX_BACKOFF = 300


class MicrosoftSentineldConnector(Connector):
    module: MicrosoftSentinelModule
    configuration: MicrosoftSentinelConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(days=1),
            ignore_older_than=timedelta(days=30),
        )
        self.from_date = self.cursor.offset

        # names of the incidents already forwarded -> their createdTimeUtc (used to prune the lookback window)
        self._forwarded: LRUCache[str, datetime] = LRUCache(maxsize=DEDUP_CACHE_SIZE)
        self._dedup_store = PersistentJSON(DEDUP_KEYS_FILE, self.data_path)
        self._load_dedup_keys()

    @property
    def incidents_filter(self) -> str:
        # `ge` on a window before the checkpoint: incidents sharing the checkpoint date or written late are
        # collected again, the already forwarded ones are deduplicated
        window_start = self._to_RFC3339(self.from_date - LOOKBACK)
        return f"properties/createdTimeUtc ge {window_start}"

    @cached_property
    def batch_limit(self) -> int:
        # chunk_size is an upper bound, capped to MAX_BATCH_SIZE, with a floor of 1
        return max(1, min(self.configuration.chunk_size, MAX_BATCH_SIZE))

    @cached_property
    def client(self) -> SecurityInsights:
        credential = ClientSecretCredential(
            tenant_id=self.module.configuration.tenant_id,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )
        return SecurityInsights(
            credential=credential,
            subscription_id=self.module.configuration.subscription_id,
        )

    @staticmethod
    def _as_utc(date: datetime | None) -> datetime | None:
        """
        Convert a datetime to UTC. Naive datetimes are considered as UTC.
        """
        if date is None:
            return None
        if date.tzinfo is None:
            return date.replace(tzinfo=UTC)
        return date.astimezone(UTC)

    def _to_RFC3339(self, date: datetime | None) -> str | None:  # noqa: N802
        """
        Format a datetime as RFC3339 in UTC. Naive datetimes are considered as UTC.
        """
        utc_date = self._as_utc(date)
        return utc_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if utc_date else None

    def _incidents_iterator(self) -> ItemPaged[Incident]:
        return self.client.incidents.list(
            resource_group_name=self.module.configuration.resource_group,
            workspace_name=self.module.configuration.workspace_name,
            filter=self.incidents_filter,
            orderby=INCIDENTS_ORDER_BY,
        )  # type: ignore

    def _get_incident_entities(self, incident_id: str) -> list[dict[str, Any]]:
        """
        Fetch entities for a given incident.

        Azure errors and malformed entities (deserialization or conversion errors) are charged to this
        incident: they are logged and counted, and the incident is forwarded without entities.
        Any other exception is a bug and propagates.
        """
        try:
            response = self.client.incidents.list_entities(
                resource_group_name=self.module.configuration.resource_group,
                workspace_name=self.module.configuration.workspace_name,
                incident_id=incident_id,
            )
            entities: Any = getattr(response, "entities", None)
            if not entities:
                return []

            parsed_entities = []
            for entity in entities:
                # the Azure SDK keeps null entries of a malformed list as None
                if entity is None:
                    continue
                parsed_entities.append(entity.as_dict())

            return parsed_entities

        except (AzureError, KeyError, TypeError, ValueError) as e:
            # DeserializationError (malformed entities) is a ValueError, not an AzureError
            self.log(
                message=f"Failed to fetch entities for incident {incident_id}, forwarding it without entities: {e}",
                level="warning",
            )
            ENTITIES_FETCH_ERRORS.labels(intake_key=self.configuration.intake_key).inc()
            return []

    def _serialize_incident(self, incident: Incident) -> dict[str, Any]:
        keys_to_extract = list(MicrosoftSentinelResponseModel.model_fields.keys())
        conversion_map: dict[type, Callable[[Any], Any]] = {
            IncidentAdditionalData: additional_data_to_dict,
            IncidentOwnerInfo: owner_data_to_dict,
            date_time.datetime: lambda dt: dt.isoformat(),
        }
        new_dict: dict[str, Any] = {}

        for key in keys_to_extract:
            value = getattr(incident, key, None)
            if isinstance(value, list) and all(isinstance(item, IncidentLabel) for item in value):
                new_dict[key] = [labels_data_to_dict(item) for item in value]
            elif type(value) in conversion_map:
                new_dict[key] = conversion_map[type(value)](value)
            else:
                # any other msrest / azure model (e.g. system_data: SystemData) is converted to a dict
                as_dict = getattr(value, "as_dict", None)
                new_dict[key] = as_dict() if callable(as_dict) else value

        return new_dict

    def _dedup_key(self, incident: Incident) -> str | None:
        """
        Key identifying an incident: its name. An incident is forwarded once, its later updates are not.
        Incidents without a creation date cannot be checkpointed nor pruned from the window: no key.
        """
        name = getattr(incident, "name", None)
        if not name or incident.created_time_utc is None:
            return None
        return str(name)

    def _load_dedup_keys(self) -> None:
        with self._dedup_store as store:
            keys: dict[str, str] = store.get("keys", {})

        incidents = sorted((datetime.fromisoformat(created), name) for name, created in keys.items())
        # insert the oldest incidents first so they are the first evicted from the LRU cache
        for created, name in incidents:
            self._forwarded[name] = created

    def _save_dedup_keys(self) -> None:
        """
        Persist the incidents forwarded within the lookback window, and forget the older ones: they are
        no longer returned by the incidents query.
        """
        window_start = self.cursor.offset - LOOKBACK
        for name, created in list(self._forwarded.items()):
            if created < window_start:
                del self._forwarded[name]

        with self._dedup_store as store:
            store.clear()
            store["keys"] = {name: created.isoformat() for name, created in self._forwarded.items()}

    def _forward_batch(self, batch: list[EventType], created_dates: list[tuple[str | None, datetime | None]]) -> None:
        """
        Push a batch of incidents, then advance the checkpoint to the most recent forwarded creation date.

        Incidents are requested in ascending createdTimeUtc order, so once a batch is pushed every
        incident created before its most recent date has been forwarded. A later failure in the same poll
        resumes from this batch instead of collecting the already pushed ones again.

        The SDK logs and swallows the errors of the intake: if fewer event ids than events sent are returned,
        nothing is marked as forwarded nor checkpointed, and IncidentsForwardError is raised.
        """
        # the SDK silently discards events bigger than EVENT_BYTES_MAX_SIZE (measured on the string length):
        # drop them here, so the number of returned event ids can be compared with the number of events sent
        events: list[EventType] = []
        for event, (key, _) in zip(batch, created_dates, strict=True):
            if len(str(event)) > EVENT_BYTES_MAX_SIZE:
                self.log(
                    message=f"Incident {key} is bigger than {EVENT_BYTES_MAX_SIZE} bytes and cannot be forwarded",
                    level="warning",
                )
            else:
                events.append(event)

        if events:
            self.log(message=f"Sending batch of {len(events)} messages", level="info")
            event_ids = self.push_events_to_intakes(events=events)
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(event_ids))
            if len(event_ids) < len(events):
                raise IncidentsForwardError(
                    f"Only {len(event_ids)} of {len(events)} incidents were accepted by the intake"
                )

        for key, created in created_dates:
            if key is not None and created is not None:
                self._forwarded[key] = created

        dates = [created for _, created in created_dates if created is not None]
        if dates:
            # the checkpoint setter only persists dates more recent than the current checkpoint, so a batch of
            # late incidents does not move it backward
            self.cursor.offset = max(dates)
            self.from_date = self.cursor.offset
            self._save_dedup_keys()

    def get_incidents(self) -> None:
        self.log(message="Start fetching alerts from Microsoft sentinel", level="info")

        batch: list[EventType] = []
        created_dates: list[tuple[str | None, datetime | None]] = []
        seen_in_poll: set[str] = set()
        collected = 0
        duplicates = 0
        for item in self._incidents_iterator():
            key = self._dedup_key(item)
            if key is not None:
                if key in self._forwarded or key in seen_in_poll:
                    # this incident was already forwarded (lookback window of the query)
                    duplicates += 1
                    continue
                seen_in_poll.add(key)

            collected += 1
            INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc()

            serialized_incident = self._serialize_incident(item)
            incident_id = getattr(item, "name", None)
            if incident_id:
                serialized_incident["entities"] = self._get_incident_entities(incident_id)

            # default=str: an unexpected field type must not crash the whole poll
            batch.append(orjson.dumps(serialized_incident, default=str).decode("utf-8"))
            created_dates.append((key, self._as_utc(item.created_time_utc)))

            if len(batch) >= self.batch_limit:
                self._forward_batch(batch, created_dates)
                batch, created_dates = [], []

        if batch:
            self._forward_batch(batch, created_dates)

        if collected == 0:
            self.log(message=f"No new incidents to forward ({duplicates} already forwarded)", level="info")

        # lag from the most recent forwarded creation date (the checkpoint), on every poll: an idle
        # Sentinel workspace and a stuck connector both show a growing lag
        events_lag = int(time.time() - self.cursor.offset.timestamp())
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)

    def _next_wait(self, duration: int, consecutive_failures: int) -> float:
        """
        Seconds to wait before the next poll.

        After a successful poll, wait for the rest of the polling interval. After consecutive failures,
        wait exponentially longer (frequency, 2 x frequency, ...), capped to MAX_BACKOFF.
        """
        frequency = max(self.configuration.frequency, 1)
        if consecutive_failures == 0:
            return max(frequency - duration, 0)
        return float(min(frequency * 2 ** (consecutive_failures - 1), max(MAX_BACKOFF, frequency)))

    def run(self) -> None:
        trigger_start_time = datetime.now(UTC).isoformat()
        self.log(message=f"Microsoft Sentinel Trigger process initiated at {trigger_start_time}", level="info")

        consecutive_failures = 0
        try:
            while self.running:
                start = time.time()
                try:
                    self.get_incidents()
                    consecutive_failures = 0

                except (AzureError, DeserializationError, HTTPError, BaseHTTPError, IncidentsForwardError) as ex:
                    # API errors, incidents the Azure SDK cannot deserialize, intake failures: nothing unpushed
                    # was checkpointed, retry with a backoff (log_exception logs at the error level)
                    consecutive_failures += 1
                    self.log_exception(
                        ex, message=f"Failed to fetch incidents ({consecutive_failures} consecutive failures)"
                    )
                except Exception as ex:
                    self.log_exception(ex, message="An unknown exception occurred")
                    raise

                duration = int(time.time() - start)
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                wait = self._next_wait(duration, consecutive_failures)
                if wait > 0:
                    # interruptible wait: returns as soon as stop() sets the SDK stop event
                    self._stop_event.wait(wait)
        finally:
            trigger_end_time = datetime.now(UTC).isoformat()
            self.log(message=f"Microsoft Sentinel Trigger process has stopped at {trigger_end_time}", level="info")
