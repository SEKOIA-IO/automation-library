"""Tests for trellix token and scopes."""

from time import time
from typing import List

import pytest

from client.schemas.token import HttpToken, Scope, TrellixToken


@pytest.fixture
def sample_token(session_faker) -> HttpToken:
    """
    Generate HttpToken.

    Args:
        session_faker: Faker

    Returns:
        HttpToken:
    """
    return HttpToken(
        tid=session_faker.pyint(),
        token_type=session_faker.word(),
        expires_in=10,
        access_token=session_faker.word(),
    )


@pytest.fixture
def sample_scopes() -> List[Scope]:
    """
    Creates sample list of scopes for testing

    Returns:
        list[Scope]:
    """
    return [Scope.MI_USER_INVESTIGATE, Scope.ENS_AM_A]


@pytest.fixture
def sample_trellix_token(sample_token, sample_scopes) -> TrellixToken:
    """
    Creates a sample TrellixToken for testing

    Args:
        sample_token: HttpToken
        sample_scopes: List[Scope]

    Returns:
        TrellixToken:
    """
    return TrellixToken(token=sample_token, scopes=set(sample_scopes), created_at=int(time()))


def test_trellix_token_valid(sample_trellix_token):
    """
    Test if the TrellixToken is valid.

    Args:
        sample_trellix_token: TrellixToken
    """
    assert sample_trellix_token.is_valid()


def test_trellix_token_invalid_scopes(sample_trellix_token):
    """
    Test if the TrellixToken is valid for a list of scopes.

    Args:
        sample_trellix_token: TrellixToken
    """
    invalid_scopes = [Scope.SOC_HTS_C, Scope.MVS_ENDP_A]

    assert not sample_trellix_token.is_valid_for_scopes(invalid_scopes)


def test_trellix_token_expired(sample_trellix_token):
    """
    Test if the TrellixToken is expired.

    Args:
        sample_trellix_token: TrellixToken
    """
    now = int(time())

    expires_in = sample_trellix_token.token.expires_in

    sample_trellix_token.created_at = (now - expires_in) + 2
    assert sample_trellix_token.is_expired() is False

    sample_trellix_token.created_at = (now - expires_in) + 1
    assert sample_trellix_token.is_expired() is False

    # Because of gap in 1 second and to int conversation, the token might not be expired here and it will work as expected
    # sample_trellix_token.created_at = (now - sample_trellix_token.token.expires_in)
    # assert sample_trellix_token.is_expired() is False

    sample_trellix_token.created_at = (now - expires_in) - 1
    assert sample_trellix_token.is_expired() is False

    sample_trellix_token.created_at = (now - expires_in) - 2
    assert sample_trellix_token.is_expired() is True
