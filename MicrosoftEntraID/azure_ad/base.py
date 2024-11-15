from functools import cached_property

from azure.identity.aio import ClientSecretCredential  # async credentials only
from azure.identity import UsernamePasswordCredential
from kiota_authentication_azure.azure_identity_authentication_provider import AzureIdentityAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient
from pydantic import BaseModel, Field, root_validator
from sekoia_automation.action import Action
from sekoia_automation.module import Module

import sentry_sdk
from traceback import format_exc
import asyncio


class AzureADConfiguration(BaseModel):
    tenant_id: str = Field(..., description="ID of the Azure AD tenant")
    username: str = Field(..., description="")
    password: str = Field(secret=True, description="")
    client_id: str = Field(
        ...,
        description="Client ID. An application needs to be created in the Azure Portal and assigned relevent permissions. Its Client ID should then be used in this configuration.",  # noqa: E501
    )
    client_secret: str = Field(
        secret=True,
        description="Client Secret associated with the registered application. Admin Consent has to be granted to the application for it to work.",  # noqa: E501
    )


class AzureADModule(Module):
    configuration: AzureADConfiguration


class AsyncAction(Action):
    def execute(self) -> None:
        try:
            self._ensure_data_path_set()
            self.set_task_as_running()
            self._results = asyncio.run(self.run(self.arguments))
        except Exception:
            self.error(f"An unexpected error occured: {format_exc()}")
            sentry_sdk.capture_exception()

        self.send_results()


class MicrosoftGraphAction(AsyncAction):
    module: AzureADModule

    _client: GraphServiceClient | None = None

    @cached_property
    def client(self) -> GraphServiceClient:
        if self._client is None:
            credentials = ClientSecretCredential(
                tenant_id=self.module.configuration.tenant_id,
                client_id=self.module.configuration.client_id,
                client_secret=self.module.configuration.client_secret,
            )
            auth_provider = AzureIdentityAuthenticationProvider(credentials)
            adapter = GraphRequestAdapter(auth_provider)
            self._client = GraphServiceClient(request_adapter=adapter)

        return self._client

    @cached_property
    def delegated_client(self):
        """
        Used for password reset action
        It's a not a good practice to use. but we app permission
        not supported for this action
        """
        credentials = UsernamePasswordCredential(
            client_id=self.module.configuration.client_id,
            username=self.module.configuration.username,
            password=self.module.configuration.password,
        )

        return GraphServiceClient(credentials=credentials)


class ApplicationArguments(BaseModel):
    objectId: str | None = Field(None, description="ID object of the app. you can find it in the app overview.")


class IdArguments(BaseModel):
    id: str | None = Field(None, description="ID of the user. id should be specified.")


class SingleUserArguments(BaseModel):
    id: str | None = Field(None, description="ID of the user. id or userPrincipalName should be specified.")
    userPrincipalName: str | None = Field(
        None,
        description="Principal Name of the user. id or userPrincipalName should be specified.",
    )


class RequiredSingleUserArguments(SingleUserArguments):
    @root_validator
    def validate_id_or_userPrincipalName(cls, values):
        if not (values.get("id") or values.get("userPrincipalName")):
            raise ValueError("'id' or 'userPrincipalName' should be specified")

        return values


class RequiredTwoUserArguments(SingleUserArguments):
    userNewPassword: str | None = Field(
        None,
        description="New password, required to reset the old one of course.",
    )

    @root_validator
    def validate_two_arguments(cls, values):
        if not ((values.get("id") or values.get("userPrincipalName")) and values.get("userNewPassword")):
            raise ValueError("'userPrincipalName' and ('id' or 'userPrincipalName') should be specified")

        return values
