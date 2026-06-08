from requests import Session
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict

from urllib3.util.retry import Retry

from sekoia_automation.action import Action
from sekoiaio.utils import user_agent


class BaseSolAction(Action):
    """Base class for all actions related to SOL queries, providing common utilities and configurations."""

    # Common utilities and configurations for all actions can be defined here
    # For example, you could include methods for authentication, logging, etc.
    def configure_http_session(self) -> None:
        """Configure the HTTP session with retry and auth headers."""

        # Configure http with retry strategy
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
