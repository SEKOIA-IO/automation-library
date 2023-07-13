from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse
import time

from functools import cached_property

import orjson
from requests.exceptions import HTTPError
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from sophos_module.base import SophosConnector
from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.metrics import INCOMING_EVENTS, OUTCOMING_EVENTS, FORWARD_EVENTS_DURATION


class SophosXDRQueryConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000


class SophosXDRQueryTrigger(SophosConnector):
    """
    The Sophos XDR Qyery reads the messages exposed after quering the Sophos Data Lake
    API and forward it to the playbook run.

    Good to know : This's the parent class for all other query classes
    """

    configuration: SophosXDRQueryConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.query = ""
        self.from_date = self.most_recent_date_seen
        self.events_sum = 0

    @property
    def most_recent_date_seen(self):
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

            # if undefined, retrieve events from the last minute
            if most_recent_date_seen_str is None:
                return now - timedelta(days=1)

            # parse the most recent date seen
            most_recent_date_seen = isoparse(most_recent_date_seen_str)

            # We don't retrieve messages older than one week
            one_week_ago = now - timedelta(days=90)
            if most_recent_date_seen < one_week_ago:
                most_recent_date_seen = one_week_ago

            return most_recent_date_seen

    @cached_property
    def pagination_limit(self):
        return max(self.configuration.chunk_size, 1000)

    @cached_property
    def client(self):
        auth = SophosApiAuthentication(
            api_host=self.module.configuration.api_host,
            authorization_url=self.module.configuration.oauth2_authorization_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )
        return SophosApiClient(auth=auth)

    def run(self):
        self.log(message="Sophos Events Trigger has started", level="info")

        try:
            start = time.time()

            self.getting_results(self.pagination_limit)

            duration = int(time.time() - start)
            FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

        except HTTPError as ex:
            self.log_exception(ex, message="Failed to get next batch of events")
        except Exception as ex:
            self.log_exception(ex, message="An unknown exception occurred")
            raise

    def post_query(self, query: dict):
        # It's the first step of our query treatment.
        # Posting the query
        self.log(message="Starting the first step of quering the Sophos data lake", level="info")
        response_runQuery = self.client.run_query(json_query=query).json()

        query_id = response_runQuery.get("id")
        self.log(message=f"Getting the query id {query_id}", level="info")

        status = ""
        self.log(message=f"Starting the while loop before finishing", level="info")
        while status != "finished":
            # Give time for query to finish.
            time.sleep(2)
            # It's the Second step of our query treatment.
            # Checking the status of our query.
            response_queryStatus = self.client.get_query_status(query_id).json()
            status = response_queryStatus.get("status")
            result = response_queryStatus.get("result")

        self.log(message=f"Finishing the loop with status {status} and result {result}", level="info")

        return result, query_id

    def getting_results(self, pagination: str):
        now = datetime.now(timezone.utc)

        self.log(message=f"Using our function post_query to do the two first queries.", level="info")
        result, query_id = self.post_query(self.query)

        if result != "succeeded":
            raise Exception("Sophos request is correct and sent treatment but failed!!")

        # If the result succeed ==> get the data.
        response = self.client.get_query_results(query_id, pagination).json()
        items = response.get("items", [])
        self.log(message=f"Getting results with {len(items)} elements", level="info")
        INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(items))

        if len(items) > 0:
            messages = [orjson.dumps(message).decode("utf-8") for message in items]
            nextKey = response.get("pages").get("nextKey")
            self.log(message=f"Sending the first batch of {len(messages)} messages", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
            self.push_events_to_intakes(events=messages)
            self.events_sum += len(messages)

            while nextKey:
                grouped_data = []
                response_next_page = self.client.get_query_results_next_page(query_id, pagination, nextKey).json()
                next_page_items = response_next_page.get("items", [])
                grouped_data.extend(next_page_items)
                self.log(message=f"Sending other batches of {len(grouped_data)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(grouped_data))
                self.push_events_to_intakes(events=grouped_data)
                self.events_sum += len(grouped_data)
                nextKey = response_next_page.get("pages").get("nextKey")

            most_recent_date_seen = now
            self.from_date = most_recent_date_seen
            with self.context as cache:
                cache["most_recent_date_seen"] = most_recent_date_seen.isoformat()

        else:
            self.log(message="No messages to forward", level="info")


class SophosXDRIOCQuery(SophosXDRQueryTrigger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = {
            "adHocQuery": {"template": "SELECT * FROM xdr_ioc_view WHERE ioc_detection_weight > 3"},
            "from": self.from_date.isoformat(),
        }
