from typing import Any


class Error(Exception):
    """Base class for exceptions in this module"""


class APIError(Error):
    pass


class AuthenticationFailed(APIError):
    def __init__(
        self,
        code: str,
        description: str | None,
        uri: str | None,
        client_id: str | None,
    ):
        self.code = code
        self.description = description
        self.uri = uri
        self.client_id = client_id

    @classmethod
    def from_http_response(cls, error: dict[str, Any]) -> "AuthenticationFailed":
        return cls(
            error["error"],
            error.get("error_description"),
            error.get("error_uri"),
            error.get("client_id"),
        )

    def __str__(self) -> str:
        parts = [f"code='{self.code}'"]
        if self.description:
            parts.append(f"description='{self.description}'")

        if self.uri:
            parts.append(f"uri='{self.uri}'")

        message = "Authentication failed"

        if self.client_id:
            message = f"{message} for client '{self.client_id}'"

        if len(parts) > 0:
            message = f"{message} {' '.join(parts)}"

        return message
