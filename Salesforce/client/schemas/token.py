"""All models related to auth token workflow."""

from time import time

from pydantic import BaseModel, Field


class HttpToken(BaseModel):
    """Http model for auth token response."""

    access_token: str
    signature: str
    instance_url: str
    tid: str = Field(alias="id")
    token_type: str
    issued_at: str


class SalesforceToken(BaseModel):
    """Model to work with auth token with additional info."""

    token: HttpToken
    created_at: int
    ttl: int

    def is_valid(self) -> bool:
        """
        Check if token is not expired yet and valid for defined scopes.

        Returns:
            bool:
        """
        return not self.is_expired()

    def is_expired(self) -> bool:
        """
        Check if token is expired.

        Returns:
            bool:
        """
        return self.created_at + self.ttl < (time() - 1)
