from collections.abc import Iterator
from typing import Any

import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from slack_modules.errors import AuthenticationError, PlanError, SlackAuditLogsError

AUTHENTICATION_ERRORS = frozenset(
    {
        "not_authed",
        "invalid_auth",
        "invalid_authentication",
        "token_revoked",
        "token_expired",
        "missing_scope",
        "not_allowed_token_type",
    }
)
PLAN_ERRORS = frozenset({"paid_only", "feature_not_enabled", "org_login_required"})

REQUEST_TIMEOUT = 30


class AuditLogsClient(requests.Session):
    """Reads pages of audit events from the Slack Audit Logs API.

    Rate limiting, retries and Retry-After are delegated to the mounted LimiterAdapter and urllib3
    Retry, following the pattern of the Tehtris and SkyhighSecurity modules.
    """

    MAX_PAGES = 100

    def __init__(self, base_url: str, token: str, per_minute: int = 30, nb_retries: int = 5) -> None:
        super().__init__()
        self.logs_url = f"{base_url.rstrip('/')}/logs"
        self.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

        adapter = LimiterAdapter(
            per_minute=per_minute,
            max_retries=Retry(
                total=nb_retries,
                backoff_factor=1,
                # Empty by default, which retries connection errors only.
                status_forcelist=[429, 500, 502, 503, 504],
            ),
        )
        self.mount("https://", adapter)
        self.mount("http://", adapter)

    def iter_pages(
        self, oldest: int, latest: int, limit: int = 1000, cursor: str = ""
    ) -> Iterator[tuple[list[dict[str, Any]], str]]:
        """Yield (entries, next_cursor) for each page of the window `oldest`..`latest` (unix seconds).

        An empty next_cursor means the window is drained. A non-empty one on the last page yielded
        means the page budget ran out first; pass it back as `cursor` to carry on where this left off.
        """
        for _ in range(self.MAX_PAGES):
            parameters: dict[str, Any] = {"oldest": oldest, "latest": latest, "limit": limit}
            if cursor:
                parameters["cursor"] = cursor

            payload = self._get_logs(parameters)
            cursor = (payload.get("response_metadata") or {}).get("next_cursor") or ""

            # Yielded even when the page holds no entries: the cursor is progress the caller records.
            yield payload.get("entries") or [], cursor

            if not cursor:
                return

    def _get_logs(self, parameters: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.get(self.logs_url, params=parameters, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as error:
            raise SlackAuditLogsError(str(error)) from error

        if response.status_code in (401, 403):
            raise AuthenticationError(self._error_code(response))

        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise SlackAuditLogsError(str(error)) from error

        if not isinstance(payload, dict):
            raise SlackAuditLogsError(f"Expected a JSON object, got {type(payload).__name__}")

        if payload.get("ok") is False:
            code = self._error_code(response)
            if code in AUTHENTICATION_ERRORS:
                raise AuthenticationError(code)
            if code in PLAN_ERRORS:
                raise PlanError(code)
            raise SlackAuditLogsError(code)

        return payload

    @staticmethod
    def _error_code(response: requests.Response) -> str:
        try:
            return str(response.json().get("error", f"HTTP {response.status_code}"))
        except ValueError:
            return f"HTTP {response.status_code}"
