import datetime as date_time
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

import orjson
from azure.core.exceptions import AzureError
from azure.core.paging import ItemPaged
from azure.identity import ClientSecretCredential
from azure.mgmt.securityinsight import SecurityInsights
from azure.mgmt.securityinsight.models import Incident, IncidentAdditionalData, IncidentLabel, IncidentOwnerInfo
from cachetools import LRUCache
from requests.exceptions import HTTPError
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, EventType
from sekoia_automation.storage import PersistentJSON
from urllib3.exceptions import HTTPError as BaseHTTPError

from microsoft_sentinel import (
    MicrosoftSentinelConnectorConfiguration,
    MicrosoftSentinelModule,
    MicrosoftSentinelResponseModel,
)
from microsoft_sentinel.metrics import (
    ENTITIES_FETCH_ERRORS,
    EVENTS_LAG,
    FORWARD_EVENTS_DURATION,
    INCOMING_EVENTS,
    OUTCOMING_EVENTS,
)
from microsoft_sentinel.utils import additional_data_to_dict, labels_data_to_dict, owner_data_to_dict

MAX_BATCH_SIZE = 1000
# incidents are queried from `checkpoint - LOOKBACK` to collect the ones written late, with a modification
# date older than the checkpoint
LOOKBACK = timedelta(minutes=5)
# hard cap of the incident versions remembered (and persisted) to avoid forwarding the same version twice
DEDUP_CACHE_SIZE = 10_000
# versions forwarded within the lookback window, persisted to survive restarts
DEDUP_KEYS_FILE = "incidents_dedup.json"
INCIDENTS_ORDER_BY = "properties/lastModifiedTimeUtc asc"
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

        # versions (name + lastModifiedTimeUtc) of the incidents already forwarded -> their lastModifiedTimeUtc
        self._forwarded: LRUCache[str, datetime] = LRUCache(maxsize=DEDUP_CACHE_SIZE)
        self._dedup_store = PersistentJSON(DEDUP_KEYS_FILE, self.data_path)
        self._load_dedup_keys()

    @property
    def incidents_filter(self) -> str:
        # `ge` on a window before the checkpoint: incidents sharing the checkpoint date or written late are
        # collected again, the already forwarded versions are deduplicated
        window_start = self._to_RFC3339(self.from_date - LOOKBACK)
        return f"properties/lastModifiedTimeUtc ge {window_start}"

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

        Azure errors are logged and counted, and the incident is forwarded without entities.
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
                parsed_entities.append(entity.as_dict())

            return parsed_entities

        except AzureError as e:
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
                new_dict[key] = value

        return new_dict

    def _dedup_key(self, incident: Incident) -> str | None:
        """
        Key identifying a given version of an incident: its name and its last modification date.
        """
        name = getattr(incident, "name", None)
        last_modified = self._as_utc(incident.last_modified_time_utc)
        if not name or last_modified is None:
            return None
        return f"{name}|{last_modified.isoformat()}"

    def _load_dedup_keys(self) -> None:
        with self._dedup_store as store:
            keys: dict[str, str] = store.get("keys", {})

        versions = sorted((datetime.fromisoformat(last_modified), key) for key, last_modified in keys.items())
        # insert the oldest versions first so they are the first evicted from the LRU cache
        for last_modified, key in versions:
            self._forwarded[key] = last_modified

    def _save_dedup_keys(self) -> None:
        """
        Persist the versions forwarded within the lookback window, and forget the older ones: they are
        no longer returned by the incidents query.
        """
        window_start = self.cursor.offset - LOOKBACK
        for key, last_modified in list(self._forwarded.items()):
            if last_modified < window_start:
                del self._forwarded[key]

        with self._dedup_store as store:
            store.clear()
            store["keys"] = {key: last_modified.isoformat() for key, last_modified in self._forwarded.items()}

    def _forward_batch(self, batch: list[EventType], versions: list[tuple[str | None, datetime | None]]) -> None:
        """
        Push a batch of incidents, then advance the checkpoint to the most recent forwarded modification date.

        Incidents are requested in ascending lastModifiedTimeUtc order, so once a batch is pushed every
        incident modified before its most recent date has been forwarded. A later failure in the same poll
        resumes from this batch instead of collecting the already pushed ones again.
        """
        self.log(message=f"Sending batch of {len(batch)} messages", level="info")
        self.push_events_to_intakes(events=batch)
        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch))

        for key, last_modified in versions:
            if key is not None and last_modified is not None:
                self._forwarded[key] = last_modified

        dates = [last_modified for _, last_modified in versions if last_modified is not None]
        if dates:
            # the checkpoint setter only persists dates more recent than the current checkpoint, so a batch of
            # late incidents does not move it backward
            self.cursor.offset = max(dates)
            self.from_date = self.cursor.offset
            self._save_dedup_keys()

    def get_incidents(self) -> None:
        self.log(message="Start fetching alerts from Microsoft sentinel", level="info")

        batch: list[EventType] = []
        versions: list[tuple[str | None, datetime | None]] = []
        seen_in_poll: set[str] = set()
        collected = 0
        duplicates = 0
        for item in self._incidents_iterator():
            key = self._dedup_key(item)
            if key is not None:
                if key in self._forwarded or key in seen_in_poll:
                    # this version of the incident was already forwarded (lookback window of the query)
                    duplicates += 1
                    continue
                seen_in_poll.add(key)

            collected += 1
            INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc()

            serialized_incident = self._serialize_incident(item)
            incident_id = getattr(item, "name", None)
            if incident_id:
                serialized_incident["entities"] = self._get_incident_entities(incident_id)

            batch.append(orjson.dumps(serialized_incident).decode("utf-8"))
            versions.append((key, self._as_utc(item.last_modified_time_utc)))

            if len(batch) >= self.batch_limit:
                self._forward_batch(batch, versions)
                batch, versions = [], []

        if batch:
            self._forward_batch(batch, versions)

        if collected == 0:
            self.log(message=f"No new incidents to forward ({duplicates} already forwarded)", level="info")

        # lag from the most recent forwarded modification date (the checkpoint), on every poll: an idle
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

                except (AzureError, HTTPError, BaseHTTPError) as ex:
                    # transient API errors: nothing unpushed was checkpointed, retry with a backoff
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
