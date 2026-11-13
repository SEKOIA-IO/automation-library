from posixpath import join as urljoin

from pydantic import BaseModel
from requests import Response, Session
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

# Errors of the generative API, by HTTP status and error code: a known code with an unexpected status
# is not explained, as the message may not apply
API_ERRORS: dict[tuple[int, str], str] = {
    (404, "GE100"): "The agent '{agent_uuid}' does not exist, or the community cannot run it",
    (403, "GE112"): "Access denied to the agent '{agent_uuid}': the API key lacks the permission to run it",
    (403, "GE126"): "Defining an agent inline requires the permission to manage AI agents",
    (409, "GE127"): "The agent '{agent_uuid}' already has an active run on this scope",
    (
        403,
        "GE128",
    ): "Running the agent '{agent_uuid}' requires an Elevate subscription for the community '{community_uuid}'",
    (429, "GE118"): (
        "The monthly AI usage quota of the community '{community_uuid}' is exceeded: "
        "the agent '{agent_uuid}' was not run. "
        "Raise the quota or wait for the next month"
    ),
}


class AgentApiError(Exception):
    """Raised when the generative API rejects a request with a known error, explained in the message."""


def get_error_code(response: Response) -> str | None:
    try:
        return response.json().get("detail", {}).get("code")
    except ValueError, KeyError, TypeError:
        return None


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

    def raise_for_api_error(
        self, response: Response, error: HTTPError, agent_uuid: str, community_uuid: str | None = None
    ) -> None:
        """Raise an AgentApiError with a readable message if the response is a known error of the API.

        :param response: Response of the failed request
        :param error: HTTP error raised for the response
        :param agent_uuid: UUID of the agent the request was about
        :param community_uuid: UUID of the community the agent was run for
        """
        template = API_ERRORS.get((response.status_code, get_error_code(response) or ""))
        if template is None:
            return

        message = template.format(agent_uuid=agent_uuid, community_uuid=community_uuid)
        self.log(message, level="error")
        raise AgentApiError(message) from error

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
            self.raise_for_api_error(response, e, uuid)
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
        may still have created a run on the server. Neither are the errors of the API: an exceeded
        quota lasts until the end of the month, and each attempt records a failed run and notifies the admins.

        :param body: Request body for executing the agent
        :return: UUID of the created agent run
        """

        fields = body.model_dump()

        response = self.http_session.post(
            url=urljoin(self.api, "agent-runs"),
            json=fields,
            timeout=60,
        )
        try:
            response.raise_for_status()
        except HTTPError as e:
            self.raise_for_api_error(response, e, fields.get("agent_uuid", ""), fields.get("community_uuid"))
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
