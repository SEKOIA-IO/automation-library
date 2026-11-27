"""Aws base client wrapper with its config class."""

import asyncio
from collections.abc import Callable
from datetime import datetime
from functools import cached_property
from typing import Any, Generic, TypeVar

from aiobotocore.credentials import AioRefreshableCredentials
from aiobotocore.session import AioCredentials, AioSession, ClientCreatorContext
from botocore.credentials import CredentialProvider
from pydantic import BaseModel, Field


class AwsClientConfiguration(BaseModel):
    """AWS client base configuration."""

    aws_access_key_id: str | None = Field(default=None, description="AWS access key id")
    aws_secret_access_key: str | None = Field(default=None, description="AWS secret access key")
    aws_region: str = Field(..., description="AWS region name")
    aws_session_token: str | None = Field(default=None, description="AWS session token")
    aws_expiration: datetime | None = Field(default=None, description="Expiration of the temporary credentials")
    credentials_refresher: Callable[[], "AwsClientConfiguration"] | None = Field(
        default=None,
        exclude=True,
        repr=False,
        description="Renews the temporary credentials. Blocking: it is called in a worker thread",
    )


AwsConfigurationT = TypeVar("AwsConfigurationT", bound=AwsClientConfiguration)


class _CredentialsProvider(CredentialProvider):
    """Custom credentials provider."""

    METHOD = "_sekoia_credentials_provider"

    def __init__(self, configuration: AwsClientConfiguration) -> None:
        """
        Initialize CredentialsProvider.

        Args:
            configuration: AwsClientConfiguration
        """
        self.configuration = configuration

    @staticmethod
    def _metadata(configuration: AwsClientConfiguration) -> dict[str, Any]:
        expiration = configuration.aws_expiration
        return {
            "access_key": configuration.aws_access_key_id,
            "secret_key": configuration.aws_secret_access_key,
            "token": configuration.aws_session_token,
            # botocore parses a string
            "expiry_time": expiration.isoformat() if expiration else None,
        }

    async def load(self) -> AioCredentials:
        """
        Load credentials.

        They renew themselves when close to expiration if the configuration can refresh them.

        Returns:
            AioCredentials
        """
        configuration = self.configuration
        refresher = configuration.credentials_refresher

        if refresher and configuration.aws_expiration:

            async def refresh() -> dict[str, Any]:
                return self._metadata(await asyncio.to_thread(refresher))

            return AioRefreshableCredentials.create_from_metadata(self._metadata(configuration), refresh, self.METHOD)

        return AioCredentials(
            access_key=configuration.aws_access_key_id,
            secret_key=configuration.aws_secret_access_key,
            token=configuration.aws_session_token,
            method=self.METHOD,
        )


class AwsClient(Generic[AwsConfigurationT]):
    """
    Aws base client.

    All other clients should extend this base client.
    """

    _configuration: AwsConfigurationT | None = None
    _credentials_provider: _CredentialsProvider | None = None

    def __init__(self, configuration: AwsConfigurationT | None = None) -> None:
        """
        Initialize AwsClient.

        Args:
            configuration: AwsConfigurationT
        """
        self._configuration = configuration

        if self._configuration:
            self._credentials_provider = _CredentialsProvider(self._configuration)

    @cached_property
    def session(self) -> AioSession:
        """
        Get AWS session.

        Returns:
            AioSession:
        """
        session = AioSession()

        # Make our own creds provider to be executed at 1 place
        if self._credentials_provider:
            credential_provider = session.get_component("credential_provider")
            credential_provider.insert_before("env", self._credentials_provider)

        return session

    def get_client(
        self,
        client_name: str,
        region_name: str | None = None,
    ) -> ClientCreatorContext:
        """
        Get AWS client.

        Args:
            client_name: str
            region_name: str | None

        Returns:
            ClientCreatorContext:
        """
        _region_name = region_name
        if not region_name and self._configuration is not None:
            _region_name = self._configuration.aws_region

        if not _region_name:
            raise ValueError("Region name is required. You should specify it.")

        return self.session.create_client(
            client_name,
            region_name=_region_name,
        )
