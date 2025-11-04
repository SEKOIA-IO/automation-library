from typing import Any

import requests
import urllib3
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from .base_get_event import BaseGetEvents


class GetEvents(BaseGetEvents):

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError),
    )
    def _get_results(self, event_search_job_uuid: str, limit: int) -> list[dict[str, Any]]:
        """
        Retrieve the results of the event search job

        :param event_search_job_uuid: The UUID of the event search job
        :param limit: The maximum number of results to retrieve
        :return: A list of events
        """
        results: list[dict[str, Any]] = []
        offset: int = 0
        total: None | int = None

        while total is None or total > offset:
            response_events = self.http_session.get(
                f"{self.events_api_path}/search/jobs/{event_search_job_uuid}/events",
                params={"limit": limit, "offset": offset},
                timeout=20,
            )
            try:
                response_events.raise_for_status()
            except requests.exceptions.HTTPError as e:
                self.log(
                    f"HTTP error when retrieving events for job {event_search_job_uuid}: {e}. Response status: {response_events.status_code}, Response text: {response_events.text}",
                    level="error",
                )
                raise

            response_content = response_events.json()
            if not response_content["items"]:
                num_results = len(results)
                if num_results < response_content["total"] and num_results < limit:
                    self.log(
                        "Number of fetched results doesn't match total",
                        level="error",
                        num_results=num_results,
                        total=response_content["total"],
                        search_job=event_search_job_uuid,
                    )
                break
            results += response_content["items"]
            total = min(response_content["total"], limit)

            offset += limit

        return results

    def run(self, arguments):
        limit = min(self.MAX_LIMIT, arguments.get("limit") or self.DEFAULT_LIMIT)
        self.configure_http_session()

        # Trigger the event search job
        event_search_job_uuid: str = self.trigger_event_search_job(
            query=arguments["query"],
            earliest_time=arguments["earliest_time"],
            latest_time=arguments["latest_time"],
            limit=limit,
        )

        # Wait for the search job to complete
        self.wait_for_search_job_execution(event_search_job_uuid=event_search_job_uuid)

        # Retrieve the results
        results = self._get_results(event_search_job_uuid=event_search_job_uuid, limit=limit)

        return {"events": results}
