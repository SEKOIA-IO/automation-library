from datetime import UTC, datetime
from typing import Any, cast

from requests import Response

from client import ApiClient
from mokn.domain import AttemptDetail, AttemptQuery, AttemptSummary


class AttemptRepository:
    """Fetch raw MokN attempts from the API and map them to domain objects."""

    def __init__(self, client: ApiClient, verify_ssl: bool):
        """Create a repository bound to a configured MokN API client."""

        self.client = client
        self.verify_ssl = verify_ssl

    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a MokN API request and return the decoded JSON body."""

        response: Response = self.client.request(
            method=method,
            url=url,
            json=json_body,
            params=params,
            timeout=30,
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    @staticmethod
    def parse_datetime(value: str) -> datetime:
        """Parse a MokN datetime string into a UTC-aware datetime."""

        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(UTC)

    @staticmethod
    def to_mokn_datetime(value: datetime) -> str:
        """Serialize a datetime to the format expected by MokN filters."""

        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def build_filters(self, start: datetime, query: AttemptQuery) -> dict[str, Any]:
        """Build the POST body used to list attempts from a given point in time."""

        return {
            "filters": {
                "global_operator": "and",
                "filters": [
                    {
                        "id": "status",
                        "values": query.statuses,
                        "operator": "equals",
                    },
                    {
                        "id": "datetime_from",
                        "values": self.to_mokn_datetime(start),
                        "operator": "equals",
                    },
                    {
                        "id": "type",
                        "values": [level.value for level in query.threat_levels],
                        "operator": "equals",
                    },
                ],
                "pending": query.pending,
            }
        }

    def list_attempts(self, start: datetime, query: AttemptQuery) -> list[AttemptSummary]:
        """Fetch summarized login attempts matching the provided query."""

        payload = self.request(
            "POST",
            f"{self.client.base_url}/api/v1/baits/logins",
            json_body=self.build_filters(start, query),
            params={"page": 1, "pageSize": query.page_size},
        )
        results = payload.get("data", {}).get("results", [])
        return [
            AttemptSummary(
                attempt_id=int(result["id"]),
                updated_time=self.parse_datetime(result["updated_time"]),
                raw=result,
            )
            for result in results
        ]

    def get_attempt_detail(self, attempt_id: int) -> AttemptDetail:
        """Fetch the detailed payload for a single MokN login attempt."""

        payload = self.request(
            "GET",
            f"{self.client.base_url}/api/v1/baits/logins/{attempt_id}",
        )
        return AttemptDetail(attempt_id=attempt_id, raw=payload.get("data", {}))

    def comment_attempt(self, attempt_id: int, comment: str) -> dict[str, Any]:
        """Update the comment attached to a MokN login attempt."""

        return self.request(
            "PUT",
            f"{self.client.base_url}/api/v1/baits/logins/{attempt_id}",
            json_body={"comment": comment},
        )

    def request_credential_check(self, attempt_id: int) -> dict[str, Any]:
        """Trigger a credential check for the given MokN login attempt."""

        return self.request(
            "PUT",
            f"{self.client.base_url}/api/v1/baits/logins/{attempt_id}",
            json_body={"status": -2},
        )
