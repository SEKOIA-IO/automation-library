from typing import Any


class SophosApiAuthenticationError(Exception):
    """Custom exception for authentication errors."""

    pass


class SophosGraphQLError(Exception):
    """Errors returned by a Sophos GraphQL API, even with an HTTP 200 response."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        self.codes = [(error.get("extensions") or {}).get("code") for error in errors]
        messages = [
            f"{error.get('message')} (code: {(error.get('extensions') or {}).get('code')}, path: {error.get('path')})"
            for error in errors
        ]
        super().__init__("; ".join(messages))
