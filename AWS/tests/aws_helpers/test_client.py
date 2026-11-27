"""Tests for the AWS client credentials."""

from datetime import datetime, timedelta, timezone

import pytest
from aiobotocore.credentials import AioRefreshableCredentials

from aws_helpers.client import AwsClientConfiguration, _CredentialsProvider


def _config(expiration: datetime | None = None, refresher=None, key: str = "OLD_KEY") -> AwsClientConfiguration:
    return AwsClientConfiguration(
        aws_access_key_id=key,
        aws_secret_access_key="secret",
        aws_region="us-east-1",
        aws_session_token="token",
        aws_expiration=expiration,
        credentials_refresher=refresher,
    )


@pytest.mark.asyncio
async def test_static_credentials_without_refresher():
    credentials = await _CredentialsProvider(_config()).load()

    assert not isinstance(credentials, AioRefreshableCredentials)
    assert credentials.access_key == "OLD_KEY"


@pytest.mark.asyncio
async def test_credentials_renew_themselves_close_to_expiration():
    new_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    calls: list[int] = []

    def refresher() -> AwsClientConfiguration:
        calls.append(1)
        return _config(new_expiration, key="NEW_KEY")

    credentials = await _CredentialsProvider(
        _config(datetime.now(timezone.utc) + timedelta(minutes=5), refresher)
    ).load()

    frozen = await credentials.get_frozen_credentials()

    assert frozen.access_key == "NEW_KEY"
    assert len(calls) == 1

    # renewed credentials are valid for an hour: no further renewal
    await credentials.get_frozen_credentials()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_fresh_credentials_are_not_renewed():
    def refresher() -> AwsClientConfiguration:
        raise AssertionError("must not be called")

    credentials = await _CredentialsProvider(
        _config(datetime.now(timezone.utc) + timedelta(hours=1), refresher)
    ).load()

    assert (await credentials.get_frozen_credentials()).access_key == "OLD_KEY"


@pytest.mark.asyncio
async def test_failing_refresh_is_raised_when_credentials_are_about_to_expire():
    def refresher() -> AwsClientConfiguration:
        raise RuntimeError("Could not assume role")

    credentials = await _CredentialsProvider(
        _config(datetime.now(timezone.utc) + timedelta(minutes=1), refresher)
    ).load()

    with pytest.raises(RuntimeError, match="Could not assume role"):
        await credentials.get_frozen_credentials()


@pytest.mark.asyncio
async def test_failing_refresh_keeps_the_credentials_while_they_are_still_valid():
    def refresher() -> AwsClientConfiguration:
        raise RuntimeError("Could not assume role")

    credentials = await _CredentialsProvider(
        _config(datetime.now(timezone.utc) + timedelta(minutes=12), refresher)
    ).load()

    assert (await credentials.get_frozen_credentials()).access_key == "OLD_KEY"
