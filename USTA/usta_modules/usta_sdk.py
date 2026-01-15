from typing import Any, Dict, List, Optional, Union

import requests
from requests.api import head


class UstaAPIError(Exception):
    """Raised when the USTA API returns an error."""


class UstaClient:
    BASE_URL = "https://usta.prodaft.com/api/threat-stream/v4"

    def __init__(self, token: str, timeout: int = 15):
        """
        Create a client instance.

        Args:
            token (str): Authorization token (Bearer token).
            timeout (int): Request timeout in seconds.
        """
        if not token:
            raise ValueError("Authorization token must be provided.")

        self.token = token
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
        )

    # ────────────────────────────────────────────────────────────
    # INTERNAL REQUEST HANDLER
    # ────────────────────────────────────────────────────────────
    def _request(self, method: str, url_or_path: str, params: Optional[Dict[str, Any]] = None):
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
            raise UstaAPIError(f"Client error {response.status_code}: {detail}")

        # Ensure valid JSON response
        try:
            return response.json()
        except ValueError:
            raise UstaAPIError("Invalid JSON received from server.")

    # ────────────────────────────────────────────────────────────
    # QUERY PARAMETER BUILDER
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def _clean_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Removes None values and converts lists to comma-separated strings.
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

    # ────────────────────────────────────────────────────────────
    # MAIN ENDPOINT: Compromised Credentials Tickets
    # ────────────────────────────────────────────────────────────
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
        """
        Fetch compromised credentials tickets using available filters.
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

    # ────────────────────────────────────────────────────────────
    # PAGINATION HELPER — iterate through all pages
    # ────────────────────────────────────────────────────────────
    def iter_compromised_credentials(self, **filters):
        """
        Generator that yields results from all pages automatically.
        """

        data = self.get_compromised_credentials(**filters)
        yield from data.get("results", [])

        next_url = data.get("next")

        while next_url:
            data = self._request("GET", next_url)

            yield from data.get("results", [])
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
