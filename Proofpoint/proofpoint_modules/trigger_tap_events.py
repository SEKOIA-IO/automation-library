import os
import time
from datetime import datetime, timedelta, timezone
from functools import cached_property

import orjson
import requests
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from proofpoint_modules.metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class TAPConfig(DefaultConnectorConfiguration):
    api_host: str
    client_principal: str
    client_secret: str
    frequency = 60


class TAPEventsTrigger(Connector):
    """
    The Proofpoint TAP trigger reads the next batch of messages exposed by the Proofpoint TAP
    APIs and forward it to the playbook run.

    Quick notes
    - Authentication on API is basic authentication with a principal and a secret
    - Pagination relies on the date of the last retrieval
    """

    configuration: TAPConfig

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.http_session = requests.Session()
        self.last_retrieval_date: datetime = datetime.now(timezone.utc) - timedelta(minutes=5)

    @cached_property
    def authentication(self):
        return requests.auth.HTTPBasicAuth(self.configuration.client_principal, self.configuration.client_secret)

    @cached_property
    def frequency(self):
        """
        Return the refresh frequency. Minimal to 60 seconds
        """
        return max(self.configuration.frequency, 60)

    def run(self):  # pragma: no cover
        self.log(message="ProofPoint Events Trigger has started", level="info")

        while self.running:
            try:
                self.forward_next_batch()
            except Exception as ex:
                self.log_exception(ex, message="An unknown exception occurred")
                raise

            time.sleep(self.frequency)

    def get_next_events(self, from_date: datetime) -> dict | None:
        # We don't retrieve messages older than one hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        if from_date < one_hour_ago:
            from_date = one_hour_ago

        # set parameters
        parameters = {"sinceTime": from_date.strftime(RFC3339_STRICT_FORMAT), "format": "json"}

        # get the events
        response = self.http_session.get(
            url=(f"{self.configuration.api_host}/v2/siem/all"),
            params=parameters,
            auth=self.authentication,
        )

        # something failed
        if not response.ok:
            self.log(
                message=(
                    "Request on Proofpoint TAP API to fetch events "
                    f"failed with status {response.status_code} - {response.reason}"
                ),
                level="error",
            )

            return None

        return response.json()

    def forward_next_batch(self) -> None:
        """
        Fetch next events and forward them
        """
        start = time.time()

        # get the last events from the API
        response = self.get_next_events(self.last_retrieval_date)

        # if the reponse is unavailable, do nothing
        if response is None:
            return

        # update the retrieval date for the next batch
        self.last_retrieval_date = isoparse(response["queryEndTime"])

        events: list[str] = []
        for message in response.get("messagesDelivered", []):
            message["status"] = "delivered"
            message["type"] = "message"
            events.append(orjson.dumps(message).decode("utf-8"))

        for message in response.get("messagesBlocked", []):
            message["status"] = "blocked"
            message["type"] = "message"
            events.append(orjson.dumps(message).decode("utf-8"))

        for message in response.get("clicksPermitted", []):
            message["status"] = "permitted"
            message["type"] = "click"
            events.append(orjson.dumps(message).decode("utf-8"))

        for message in response.get("clicksBlocked", []):
            message["status"] = "blocked"
            message["type"] = "click"
            events.append(orjson.dumps(message).decode("utf-8"))

        if len(events) > 0:
            self.log(
                message=(f"forward {len(events)} events"),
                level="info",
            )
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))
            self.push_events_to_intakes(events=events)
        else:
            self.log(
                message="No events to forward",
                level="info",
            )

        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(time.time() - start)
