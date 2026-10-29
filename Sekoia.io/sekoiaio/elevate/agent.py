from posixpath import join as urljoin

from pydantic import BaseModel
from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError, Timeout
from requests.structures import CaseInsensitiveDict
from sekoia_automation.action import Action
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from urllib3.exceptions import TimeoutError as Urllib3TimeoutError
from urllib3.util.retry import Retry

from sekoiaio.utils import user_agent


class BaseAgent(Action):
    api: str

    def configure_http_session(self) -> None:
        retry_strategy = Retry(
            total=10,  # Total number of retries for all types of errors
            status=10,  # Number of retries specifically for responses with status codes in status_forcelist
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1,
            backoff_max=120,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.http_session = Session()
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)
        self.http_session.headers = CaseInsensitiveDict(
            data={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.module.configuration['api_key']}",
                "User-Agent": user_agent(),
            }
        )

    def configure_url(self) -> None:
        self.api = urljoin(self.module.configuration["base_url"], "api/v1/generative")

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def get_agent(self, uuid: str) -> dict:
        """Retrieve an agent by its UUID.

        :param uuid: UUID of the agent to retrieve
        :return: Agent dict
        """
        response = self.http_session.get(
            url=urljoin(self.api, f"agents/{uuid!s}"),
            timeout=60,
        )
        try:
            response.raise_for_status()
        except HTTPError as e:
            self.log(
                (
                    f"HTTP error when retrieving agent for agent_uuid '{uuid}': {e}. "
                    f"Response status: {response.status_code}, Response text: {response.text}"
                ),
                level="error",
            )
            raise
        result = response.json()
        return result

    def execute_agent(self, body: BaseModel) -> str:
        """Execute an agent with the given request body.

        Not retried: creating a run is not idempotent, and a timed-out request
        may still have created a run on the server.

        :param body: Request body for executing the agent
        :return: UUID of the created agent run
        """
        response = self.http_session.post(
            url=urljoin(self.api, "agent-runs"),
            json=body.model_dump(),
            timeout=60,
        )
        try:
            response.raise_for_status()
        except HTTPError as e:
            self.log(
                (
                    f"HTTP error when executing agent with body '{body}': {e}. "
                    f"Response status: {response.status_code}, Response text: {response.text}"
                ),
                level="error",
            )
            raise
        result = response.json()
        return str(result["uuid"])

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def get_agent_run(self, agent_run_uuid: str) -> dict:
        response = self.http_session.get(
            url=urljoin(self.api, f"agent-runs/{agent_run_uuid}"),
            timeout=60,
        )
        try:
            response.raise_for_status()
        except HTTPError as e:
            self.log(
                (
                    f"HTTP error when getting agent run '{agent_run_uuid}': {e}. "
                    f"Response status: {response.status_code}, Response text: {response.text}"
                ),
                level="error",
            )
            raise
        return response.json()
