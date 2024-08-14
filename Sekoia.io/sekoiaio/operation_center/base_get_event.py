import time
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
            total=10,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=0.2,
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

    def wait_for_search_job_execution(self, event_search_job_uuid: str) -> None:
        # wait at most 300 sec for the event search job to conclude
        max_wait_search = 300
        start_wait = time.time()

        response_get = self.http_session.get(f"{self.events_api_path}/search/jobs/{event_search_job_uuid}", timeout=20)
        response_get.raise_for_status()

        while response_get.json()["status"] != 2:
            time.sleep(1)
            response_get = self.http_session.get(
                f"{self.events_api_path}/search/jobs/{event_search_job_uuid}", timeout=20
            )
            response_get.raise_for_status()
            if time.time() - start_wait > max_wait_search:
                raise TimeoutError(f"Event search job took more than {max_wait_search}s to conclude")

    def run(self, arguments: dict):
        raise NotImplementedError()
