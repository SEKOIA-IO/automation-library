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
# number of incident versions remembered to avoid forwarding the same version twice
DEDUP_CACHE_SIZE = 10_000
# keys of the incidents sharing the checkpoint date, persisted to survive restarts
BOUNDARY_KEYS_FILE = "incidents_boundary.json"
INCIDENTS_ORDER_BY = "properties/lastModifiedTimeUtc asc"


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

        # versions (name + lastModifiedTimeUtc) of the incidents already forwarded
        self._forwarded: LRUCache[str, bool] = LRUCache(maxsize=DEDUP_CACHE_SIZE)
        self._boundary_store = PersistentJSON(BOUNDARY_KEYS_FILE, self.data_path)
        self._boundary_time: datetime | None = None
        self._boundary_keys: set[str] = set()
        self._load_boundary_keys()

    @property
    def incidents_filter(self) -> str:
        most_recent_date = self._to_RFC3339(self.from_date)
        # `ge` (and not `gt`): incidents sharing the checkpoint date are collected again and deduplicated
        return f"properties/lastModifiedTimeUtc ge {most_recent_date}"

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

    def _load_boundary_keys(self) -> None:
        with self._boundary_store as store:
            boundary_time = store.get("last_modified_time_utc")
            boundary_keys = store.get("keys", [])

        if boundary_time:
            self._boundary_time = datetime.fromisoformat(boundary_time)
            self._boundary_keys = set(boundary_keys)
            for key in self._boundary_keys:
                self._forwarded[key] = True

    def _save_boundary_keys(self) -> None:
        if self._boundary_time is None:
            return

        with self._boundary_store as store:
            store["last_modified_time_utc"] = self._boundary_time.isoformat()
            store["keys"] = sorted(self._boundary_keys)

    def _mark_forwarded(self, key: str | None, last_modified: datetime | None) -> None:
        if key is not None:
            self._forwarded[key] = True

        if key is None or last_modified is None:
            return

        # keep the keys of the incidents sharing the most recent modification date: they are returned again
        # by the next `ge` query and must not be forwarded twice, even after a restart
        if self._boundary_time is None or last_modified > self._boundary_time:
            self._boundary_time = last_modified
            self._boundary_keys = {key}
        elif last_modified == self._boundary_time and len(self._boundary_keys) < DEDUP_CACHE_SIZE:
            self._boundary_keys.add(key)

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
            self._mark_forwarded(key, last_modified)

        dates = [last_modified for _, last_modified in versions if last_modified is not None]
        if dates:
            # the checkpoint setter only persists dates more recent than the current checkpoint
            self.cursor.offset = max(dates)
            self.from_date = self.cursor.offset
            self._save_boundary_keys()

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
                    # this version of the incident was already forwarded (boundary of the `ge` filter)
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
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
            return

        # lag from the most recent forwarded modification date (the checkpoint)
        events_lag = int(time.time() - self.cursor.offset.timestamp())
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)

    def run(self) -> None:
        trigger_start_time = datetime.now(UTC).isoformat()
        self.log(message=f"Microsoft Sentinel Trigger process initiated at {trigger_start_time}", level="info")

        try:
            while self.running:
                start = time.time()
                try:
                    self.get_incidents()

                except (HTTPError, BaseHTTPError) as ex:
                    self.log_exception(ex, message="Failed to fetch next batch of events")
                except Exception as ex:
                    self.log_exception(ex, message="An unknown exception occurred")
                    raise

                duration = int(time.time() - start)
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                delta_sleep = self.configuration.frequency - duration
                if delta_sleep > 0:
                    # interruptible wait: returns as soon as stop() sets the SDK stop event
                    self._stop_event.wait(delta_sleep)
        finally:
            trigger_end_time = datetime.now(UTC).isoformat()
            self.log(message=f"Microsoft Sentinel Trigger process has stopped at {trigger_end_time}", level="info")
