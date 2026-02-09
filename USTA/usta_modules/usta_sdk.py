from typing import Any, Dict, Iterator, List, Optional, cast

from requests import RequestException
from requests.adapters import HTTPAdapter
from requests_ratelimiter import LimiterSession
from urllib3.util.retry import Retry


class UstaAPIError(Exception):
    """Raised when the USTA API returns an error."""


class UstaAuthenticationError(UstaAPIError):
    """Raised when the USTA API returns an authentication error."""


class UstaClient:
    BASE_URL = "https://usta.prodaft.com/api/threat-stream/v4"

    def __init__(self, token: str, timeout: int = 15, per_second: int = 3):
        """Create a client instance.

        Args:
            token (str): Authorization token (Bearer token).
            timeout (int): Request timeout in seconds.
            per_second (int): Rate limit (requests per second).
        """
        if not token:
            raise ValueError("Authorization token must be provided.")

        self.token = token
        self.timeout = timeout
        self.session = LimiterSession(per_second=per_second)

        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
        )

    # ──────────────────────────────────────────────────────────────────────────
    # INTERNAL REQUEST HANDLER
    # ──────────────────────────────────────────────────────────────────────────
    def _request(self, method: str, url_or_path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Performs an HTTP request and handles errors.

        Args:
            method (str): HTTP method (e.g., "GET").
            url_or_path (str): Full URL or relative path.
            params (Optional[Dict[str, Any]]): Query parameters.

        Returns:
            Dict[str, Any]: The JSON response parsed as a dictionary.

        Raises:
            UstaAuthenticationError: If the server returns 401/403.
            UstaAPIError: For network errors, 4xx/5xx responses, or invalid JSON.
        """
        if url_or_path.startswith("http"):
            url = url_or_path
        else:
            url = f"{self.BASE_URL}/{url_or_path.lstrip('/')}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.timeout,
            )
        except RequestException as e:
            raise UstaAPIError(f"Network request failed: {str(e)}") from e

        # Basic network error handling
        if response.status_code >= 500:
            raise UstaAPIError(f"Server error {response.status_code}: {response.text}")

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text

            if response.status_code in {401, 403}:
                raise UstaAuthenticationError(f"Authentication failed ({response.status_code}): {detail}")

            raise UstaAPIError(f"Client error {response.status_code}: {detail}")

        # Ensure valid JSON response
        try:
            # Type assertion: We expect the API to always return a dictionary (JSON Object)
            data = response.json()
            if not isinstance(data, dict):
                raise UstaAPIError("Invalid JSON format: Expected a dictionary.")
            return cast(Dict[str, Any], data)
        except ValueError:
            raise UstaAPIError("Invalid JSON received from server.")

    # ──────────────────────────────────────────────────────────────────────────
    # QUERY PARAMETER BUILDER
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _clean_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Removes None values and converts lists to comma-separated strings.

        Args:
            params (Dict[str, Any]): Raw parameters.

        Returns:
            Dict[str, Any]: Cleaned parameters ready for the request.
        """
        clean = {}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, list):
                clean[key] = ",".join(str(v) for v in value)
            else:
                clean[key] = value
        return clean

    # ──────────────────────────────────────────────────────────────────────────
    # MAIN ENDPOINT: Compromised Credentials Tickets
    # ──────────────────────────────────────────────────────────────────────────
    def get_compromised_credentials(
        self,
        page: Optional[int] = None,
        size: Optional[int] = None,
        company_id: Optional[List[str]] = None,
        end: Optional[str] = None,
        is_corporate: Optional[bool] = None,
        ordering: Optional[List[str]] = None,
        password: Optional[str] = None,
        password_complexity_score: Optional[List[str]] = None,
        password_contains: Optional[List[str]] = None,
        source: Optional[List[str]] = None,
        start: Optional[str] = None,
        status: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Fetch compromised credentials tickets using available filters.

        Args:
            page (Optional[int]): Page number.
            size (Optional[int]): Page size.
            company_id (Optional[List[str]]): Filter by company IDs.
            end (Optional[str]): End date filter (ISO format).
            is_corporate (Optional[bool]): Filter by corporate status.
            ordering (Optional[List[str]]): Sorting fields.
            password (Optional[str]): Filter by password.
            password_complexity_score (Optional[List[str]]): Filter by complexity.
            password_contains (Optional[List[str]]): Filter by password content.
            source (Optional[List[str]]): Filter by source.
            start (Optional[str]): Start date filter (ISO format).
            status (Optional[List[str]]): Filter by status.

        Returns:
            Dict[str, Any]: The API response containing results and pagination info.
        """
        params = self._clean_params(
            {
                "page": page,
                "size": size,
                "company_id": company_id,
                "end": end,
                "is_corporate": is_corporate,
                "ordering": ordering,
                "password": password,
                "password_complexity_score": password_complexity_score,
                "password_contains": password_contains,
                "source": source,
                "start": start,
                "status": status,
            }
        )

        return self._request(
            "GET",
            "/security-intelligence/account-takeover-prevention/compromised-credentials-tickets",
            params=params,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PAGINATION HELPER — iterate through all pages
    # ──────────────────────────────────────────────────────────────────────────
    def iter_compromised_credentials(self, **filters: Any) -> Iterator[Dict[str, Any]]:
        """Generator that yields results from all pages automatically.

        Args:
            **filters (Any): Arbitrary keyword arguments passed to `get_compromised_credentials`.

        Yields:
            Iterator[Dict[str, Any]]: Individual compromised credential events.
        """
        data = self.get_compromised_credentials(**filters)
        # Type check for 'results' list
        results = data.get("results", [])
        if isinstance(results, list):
            yield from results

        next_url = data.get("next")

        while next_url and isinstance(next_url, str):
            data = self._request("GET", next_url)

            results = data.get("results", [])
            if isinstance(results, list):
                yield from results

            next_url = data.get("next")


# ────────────────────────────────────────────────────────────────────
# Example Usage
# ────────────────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     client = UstaClient(token="...")
#     try:
#         # Fetch a single page
#         page1 = client.get_compromised_credentials(size=10, ordering=["-created"])
#         print("Count:", page1["count"])
#         print("First item:", page1["results"][0] if page1["results"] else "No results")
#         # Iterate through all pages
#         for item in client.iter_compromised_credentials(
#             password_complexity_score=["very_weak", "weak"]
#         ):
#             print("User:", item["content"]["username"])
#     except UstaAPIError as e:
#         print("Error:", e)
