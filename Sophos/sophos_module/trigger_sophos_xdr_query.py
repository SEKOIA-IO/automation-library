from functools import cached_property
import time
import os

import orjson
from requests.exceptions import HTTPError
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.metrics import PrometheusExporterThread, make_exporter

from sophos_module.base import SophosConnector
from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.metrics import INCOMING_EVENTS, OUTCOMING_EVENTS, FORWARD_EVENTS_DURATION


class SophosXDRQueryConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000
    query: dict


class SophosXDRQueryTrigger(SophosConnector):
    """
    The Sophos XDR Qyery reads the messages exposed after quering the Sophos Data Lake
    API and forward it to the playbook run.
    """

    configuration: SophosXDRQueryConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._exporter = None

    def start_monitoring(self):
        super().start_monitoring()
        # start the prometheus exporter
        self._exporter = make_exporter(
            PrometheusExporterThread, int(os.environ.get("WORKER_PROM_LISTEN_PORT", "8010"), 10)
        )
        self._exporter.start()

    def stop_monitoring(self):
        super().stop_monitoring()
        if self._exporter:
            self._exporter.stop()

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
        response_runQuery = self.client.run_query(json_query=query).json()

        query_id = response_runQuery.get("id")

        status = ""
        while status != "finished":
            # Give time for query to finish.
            time.sleep(2)
            # It's the Second step of our query treatment.
            # Checking the status of our query.
            response_queryStatus = self.client.get_query_status(query_id).json()
            status = response_queryStatus.get("status")
            result = response_queryStatus.get("result")

        return result, query_id

    def getting_results(self, pagination: str):
        result, query_id = self.post_query(self.configuration.query)

        if result != "succeeded":
            raise Exception("Sophos request is correct and sent treatment but failed!!")

        # If the result succeed ==> get the data.
        response = self.client.get_query_results(query_id, pagination).json()
        items = response.get("items", [])
        INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(items))

        if len(items) > 0:
            messages = [orjson.dumps(message).decode("utf-8") for message in items]
            nextKey = response.get("pages").get("nextKey")

            # The case where there's no pagination in the response.
            if not nextKey:
                self.log(message=f"Sending the first batch of {len(messages)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
                self.push_events_to_intakes(events=messages)

            while nextKey:
                grouped_data = []
                response_next_page = self.client.get_query_results_next_page(query_id, pagination, nextKey).json()
                next_page_items = response_next_page.get("items", [])
                grouped_data.extend(next_page_items)
                self.log(message=f"Sending other batches of {len(grouped_data)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(grouped_data))
                self.push_events_to_intakes(events=grouped_data)
                nextKey = response_next_page.get("pages").get("nextKey")

        else:
            self.log(message="No messages to forward", level="info")
