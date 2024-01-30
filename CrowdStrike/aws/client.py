"""Aws base client wrapper with its config class."""

from functools import cached_property
from typing import Generic, TypeVar

from aiobotocore.session import AioCredentials, AioSession, ClientCreatorContext
from botocore.credentials import CredentialProvider
from pydantic import BaseModel, Field


class AwsConfiguration(BaseModel):
    """AWS client base configuration."""

    aws_access_key_id: str = Field(description="AWS access key id")
    aws_secret_access_key: str = Field(description="AWS secret access key")
    aws_region: str = Field(description="AWS region name")


AwsConfigurationT = TypeVar("AwsConfigurationT", bound=AwsConfiguration)


class _CredentialsProvider(CredentialProvider):
    """Custom credentials provider."""

    METHOD = "_crowdstrike_credentials_provider"

    def __init__(self, access_key: str, secret_key: str) -> None:
        """
        Initialize CredentialsProvider.

        Args:
            access_key: str
            secret_key: str
        """
        self.access_key = access_key
        self.secret_key = secret_key

    async def load(self) -> AioCredentials:
        """
        Load credentials.

        Returns:
            ReadOnlyCredentials
        """
        return AioCredentials(
            access_key=self.access_key,
            secret_key=self.secret_key,
            method=self.METHOD,
        )


class AwsClient(Generic[AwsConfigurationT]):
    """
    Aws base client.

    All other clients should extend this base client.
    """

    _configuration: AwsConfigurationT
    _credentialsProvider: _CredentialsProvider

    def __init__(self, configuration: AwsConfigurationT) -> None:
        """
        Initialize AwsClient.

        Args:
            configuration: AwsConfigurationT
        """
        self._configuration: AwsConfigurationT = configuration
        self._credentials_provider = _CredentialsProvider(
            configuration.aws_access_key_id, configuration.aws_secret_access_key
        )

    @cached_property
    def get_session(self) -> AioSession:
        """
        Get AWS session.

        >>> from aiobotocore.credentials import AioCredentials
        AioCredentials.load_credentials() goes through credentials chain, returning the first ``Credentials``
        that could be loaded.

        Logic for loading env credentials is here:
        >>> from botocore.credentials import create_credential_resolver
        First it tries to load credentials from environment variables.
        It will check if PROFILE is set. If it is set, it will try to load credentials from it,
            otherwise something like this is at first place:
        >>> AWS_ACCESS_KEY_ID = 'xxx'
        >>> AWS_SECRET_ACCESS_KEY = 'xxx'
        >>> AWS_DEFAULT_REGION = 'xxx'

        Right now only AioCredentials workes as expected.

        Returns:
            AioSession:
        """
        session = AioSession()

        # Make our own creds provider to be executed at 1 place
        credential_provider = session.get_component("credential_provider")
        credential_provider.insert_before("env", self._credentials_provider)

        return session

    def get_client(self, client_name: str) -> ClientCreatorContext:
        """
        Get AWS client.

        Args:
            client_name: str

        Returns:
            ClientCreatorContext:
        """
        return self.get_session.create_client(client_name, region_name=self._configuration.aws_region)
