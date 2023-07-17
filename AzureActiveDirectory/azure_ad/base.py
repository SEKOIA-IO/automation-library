from functools import cached_property

from azure.identity import ClientSecretCredential
from msgraph.core import APIVersion, GraphClient
from pydantic import BaseModel, Field, root_validator
from sekoia_automation.action import Action
from sekoia_automation.module import Module


class AzureADConfiguration(BaseModel):
    tenant_id: str = Field(..., description="ID of the Azure AD tenant")
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


class MicrosoftGraphAction(Action):
    module: AzureADModule

    @cached_property
    def client(self):
        credentials = ClientSecretCredential(
            tenant_id=self.module.configuration.tenant_id,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )
        return GraphClient(
            credential=credentials,
            api_version=APIVersion.beta,
        )


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
