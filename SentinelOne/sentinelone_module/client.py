"""SentinelOne HTTP client for asset connector with rate limiting."""

import logging
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry

from sentinelone_module.helpers import clean_hostname

logger = logging.getLogger(__name__)


class SentinelOneClient:
    """HTTP client for SentinelOne API with rate limiting and retry logic."""

    def __init__(self, hostname: str, api_token: str, rate_limit_per_second: int = 10):
        """Initialize the SentinelOne HTTP client.

        Args:
            hostname: The SentinelOne instance hostname.
            api_token: The API token for authentication.
            rate_limit_per_second: Maximum requests per second (default: 10).
        """
        self.hostname = clean_hostname(hostname)
        self.api_token = api_token
        self.base_url = f"https://{self.hostname}"
        self.rate_limit_per_second = rate_limit_per_second

        # Create session with rate limiting and retry strategy
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with rate limiting and retry strategy.

        Returns:
            Configured requests.Session with rate limiter and retry logic.
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )

        # Mount LimiterAdapter with rate limiting and retries
        adapter = LimiterAdapter(
            per_second=self.rate_limit_per_second,
            max_retries=retry_strategy,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Set default headers
        session.headers.update(
            {
                "Authorization": f"ApiToken {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        return session

    def get(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Make a GET request to the SentinelOne API.

        Args:
            endpoint: The API endpoint (e.g., "/web/api/v2.1/agents").
            params: Optional query parameters.

        Returns:
            JSON response as dictionary.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        url = urljoin(self.base_url, endpoint)

        logger.debug(f"GET request to {url} with params: {params}")

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error occurred: {e}")
            raise

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.close()
