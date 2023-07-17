"""Tests related to token."""

import time

from client.schemas.token import SalesforceToken


def test_token_is_valid(http_token, faker):
    """
    Test token is valid.

    Args:
        http_token: HttpToken
        faker: Faker
    """
    token = SalesforceToken(token=http_token, created_at=time.time(), ttl=faker.pyint(10, 20))

    assert token.is_valid()
    assert token.is_expired() is False
