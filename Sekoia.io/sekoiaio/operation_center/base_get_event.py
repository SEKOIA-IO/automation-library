import time
from typing import Callable
from posixpath import join as urljoin

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.structures import CaseInsensitiveDict
from sekoia_automation.action import Action

from sekoiaio.utils import user_agent


class BaseGetEvents(Action):
    http_session: Session
    events_api_path: str

    DEFAULT_LIMIT = 100
    MAX_LIMIT = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def configure_http_session(self):
        self.events_api_path = urljoin(self.module.configuration["base_url"], "api/v1/sic/conf/events")

        # Configure http with retry strategy
        retry_strategy = Retry(
            total=10,  # Total number of retries for all types of errors
            status=10,  # Number of retries specifically for responses with status codes in status_forcelist
            status_forcelist=[400, 404, 408, 429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1,
            backoff_max=120,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.http_session = requests.Session()
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)
        self.http_session.headers = CaseInsensitiveDict(
            data={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.module.configuration['api_key']}",
                "User-Agent": user_agent(),
            }
        )

    def trigger_event_search_job(
        self, query: str, earliest_time: str, latest_time: str, limit: int | None = None
    ) -> str:
        data = {
            "term": query,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "visible": False,
        }
        if limit is not None:
            data["max_last_events"] = limit
        response_start = self.http_session.post(
            f"{self.events_api_path}/search/jobs",
            json=data,
            timeout=20,
        )
        response_start.raise_for_status()

        return response_start.json()["uuid"]

    def _wait_for_search_job_step(
        self, event_search_job_uuid: str, should_we_wait: Callable[[int], bool], action: str, timeout: int = 300
    ) -> None:
        """
        Wait for a step in the search job execution

        :param event_search_job_uuid: The UUID of the event search job
        :param should_we_wait: A function that takes the current status and returns True if we should keep waiting
        :param action: The expected action to be performed
        :param timeout: The maximum time to wait in seconds
        """
        start_wait = time.time()

        # Initial status check
        response_get = self.http_session.get(f"{self.events_api_path}/search/jobs/{event_search_job_uuid}", timeout=20)
        response_get.raise_for_status()

        # Wait for the condition to be met
        while should_we_wait(response_get.json()["status"]):
            # Wait one second before polling again
            time.sleep(1)

            # Poll the job status
            response_get = self.http_session.get(
                f"{self.events_api_path}/search/jobs/{event_search_job_uuid}", timeout=20
            )
            response_get.raise_for_status()

            # If we exceed the timeout, raise an error
            if time.time() - start_wait > timeout:
                raise TimeoutError(f"Event search job {event_search_job_uuid} took more than {timeout}s to {action}")

    def wait_for_search_job_execution(self, event_search_job_uuid: str) -> None:
        # Wait for job to start (20 min)
        self._wait_for_search_job_step(
            event_search_job_uuid,
            lambda status: status == 0,  # Wait for status to change from 0 (not started)
            "start",
            1200,
        )
        # Wait for job to complete (30 min)
        self._wait_for_search_job_step(
            event_search_job_uuid,
            lambda status: status == 1,  # Wait for status to change from 1 (in progress)
            "complete",
            1800,
        )

    def run(self, arguments: dict):
        raise NotImplementedError()
