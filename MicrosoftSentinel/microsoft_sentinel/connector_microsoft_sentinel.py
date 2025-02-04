import time
import datetime as date_time
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse

import orjson
import itertools
from typing import Dict, Any, Callable, Optional
from functools import cached_property

from urllib3.exceptions import HTTPError as BaseHTTPError
from requests.exceptions import HTTPError

from azure.identity import ClientSecretCredential
from azure.mgmt.securityinsight import SecurityInsights
from azure.core.paging import ItemPaged
from azure.mgmt.securityinsight.models import IncidentAdditionalData, IncidentOwnerInfo, Incident, IncidentLabel

from sekoia_automation.connector import Connector
from sekoia_automation.storage import PersistentJSON

from microsoft_sentinel.utils import additional_data_to_dict, owner_data_to_dict, labels_data_to_dict
from microsoft_sentinel.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_EVENTS, OUTCOMING_EVENTS
from microsoft_sentinel import (
    MicrosoftSentinelModule,
    MicrosoftSentinelResponseModel,
    MicrosoftSentinelConnectorConfiguration,
)


class MicrosoftSentineldConnector(Connector):
    module: MicrosoftSentinelModule
    configuration: MicrosoftSentinelConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def checkpoint(self) -> str:
        now = datetime.now(timezone.utc)

        with self.context as cache:
            cached_date = cache.get("cached_date")

            if cached_date is None:
                one_day_ago = now - timedelta(days=1)
                return one_day_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

            cached_datetime: datetime = isoparse(cached_date)

            one_month_ago: datetime = now - timedelta(days=30)
            return max(cached_datetime, one_month_ago).strftime("%Y-%m-%dT%H:%M:%SZ")

    @checkpoint.setter
    def checkpoint(self, last_message_date: datetime) -> None:
        with self.context as cache:
            cache["cached_date"] = last_message_date

    @property
    def incidents_filter(self) -> str:
        return f"properties/createdTimeUtc gt {self.checkpoint}"

    @cached_property
    def batch_limit(self) -> int:
        return max(self.configuration.chunk_size, 1000)

    @cached_property
    def client(self) -> SecurityInsights:
        credential = ClientSecretCredential(
            tenant_id=self.module.configuration.tenant_id,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )
        return SecurityInsights(
            credential=credential,
            subscription_id=self.configuration.subscription_id,
        )

    def _to_timestamp(self, date: str) -> float:
        RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
        return datetime.strptime(date, RFC3339_STRICT_FORMAT).timestamp()

    def _to_RFC3339(self, date: Optional[datetime]) -> Optional[str]:
        return date.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if date else None

    def _incidents_iterator(self) -> ItemPaged[Incident]:
        return self.client.incidents.list(
            resource_group_name=self.configuration.resource_group,
            workspace_name=self.configuration.workspace_name,
            filter=self.incidents_filter,
        )  # type: ignore

    def _serialize_incident(self, incident: Incident) -> Dict[str, Any]:
        keys_to_extract = list(MicrosoftSentinelResponseModel.__fields__.keys())
        conversion_map: Dict[type, Callable[[Any], Any]] = {
            IncidentAdditionalData: additional_data_to_dict,
            IncidentOwnerInfo: owner_data_to_dict,
            date_time.datetime: lambda dt: dt.isoformat(),
        }
        new_dict = {}

        for key in keys_to_extract:
            value = getattr(incident, key)
            if isinstance(value, list) and all(isinstance(item, IncidentLabel) for item in value):
                new_dict[key] = [labels_data_to_dict(item) for item in value]
            elif type(value) in conversion_map:
                new_dict[key] = conversion_map[type(value)](value)
            else:
                new_dict[key] = value

        return new_dict

    def get_incidents(self) -> None:
        self.log(message=f"Start fetching alerts from Microsoft sentinel", level="info")

        first_element, response = itertools.tee(self._incidents_iterator())
        first_item: Optional[Incident] = next(first_element, None)

        if first_item is None:
            self.log(message="No messages to forward", level="info")
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
            return

        alerts_batch = []
        final_created_time = None
        incoming_events_sum = 0
        for item in response:
            created_time = item.created_time_utc
            serialezed_incident = self._serialize_incident(item)
            jsonify_item = orjson.dumps(serialezed_incident).decode("utf-8")
            alerts_batch.append(jsonify_item)

            if final_created_time is None:
                final_created_time = created_time
            else:
                if created_time is not None:
                    final_created_time = max(final_created_time, created_time)

            if (incoming_events_sum + 1) % self.batch_limit == 0:
                alerts_len: int = len(alerts_batch)
                self.log(message=f"Sending batch of {alerts_len} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(alerts_len)
                self.push_events_to_intakes(events=alerts_batch)
                alerts_batch = []

            incoming_events_sum += 1

        if alerts_batch:
            last_alerts_len: int = len(alerts_batch)
            self.log(message=f"Sending batch of {last_alerts_len} messages", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(last_alerts_len)
            self.push_events_to_intakes(events=alerts_batch)

        INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(incoming_events_sum)

        stored_time = self._to_RFC3339(final_created_time)

        if stored_time:
            self.checkpoint = stored_time

            most_recent_timestamp = self._to_timestamp(stored_time)
            events_lag = int(time.time() - most_recent_timestamp)
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)

    def run(self) -> None:
        trigger_start_time = datetime.now().isoformat()
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
                    time.sleep(delta_sleep)
        finally:
            trigger_end_time = datetime.now().isoformat()
            self.log(message=f"Microsoft Sentinel Trigger process has stopped at {trigger_end_time}", level="info")
