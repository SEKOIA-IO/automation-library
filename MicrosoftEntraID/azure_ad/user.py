from pydantic import BaseModel

from .base import MicrosoftGraphAction, RequiredSingleUserArguments, RequiredTwoUserArguments

from msgraph.generated.models.user import User
from msgraph.generated.users.item.authentication.methods.item.reset_password.reset_password_post_request_body import (
    ResetPasswordPostRequestBody,
)
from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder


class GetUserResults(BaseModel):
    id: str | None
    accountEnabled: bool
    assignedLicenses: list | None
    city: str | None
    companyName: str | None
    country: str | None
    createdDateTime: str | None
    creationType: str | None
    deletedDateTime: str | None
    department: str | None
    displayName: str | None
    identities: list | None
    jobTitle: str | None
    lastPasswordChangeDateTime: str | None
    mail: str | None
    mobilePhone: str | None
    userPrincipalName: str | None


class GetUserAction(MicrosoftGraphAction):
    name = "Get User"
    description = "Get information about an Azure Active Directory user. Requires the User.Read.All app permission."  # noqa: E501
    # results_model doesn't support async model
    # results_model = GetUserResults

    async def query_get_user(self, user_param, req_conf):
        return await self.client.users.by_user_id(user_param).get(request_configuration=req_conf)

    async def run(self, arguments: RequiredSingleUserArguments):
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            # select requires a list of strings, so we need to convert the keys of the schema to a list
            select=list(GetUserResults.schema()["properties"].keys()),
        )
        request_configuration = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())], query_parameters=query_params
        )
        user_param = arguments.id or arguments.userPrincipalName

        response = await self.query_get_user(user_param, request_configuration)

        response.raise_for_status()

        return response.json()


class DisableUserAction(MicrosoftGraphAction):
    name = "Disable User"
    description = (
        "Disable an Azure Active Directory user. Requires the User.ReadWrite.All app permission."  # noqa: E501
    )

    async def query_disable_user(self, user_param, req_body, req_conf):
        return await self.client.users.by_user_id(user_param).patch(body=req_body, request_configuration=req_conf)

    async def run(self, arguments: RequiredSingleUserArguments):
        request_body = User(account_enabled=False)
        request_configuration = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )
        user_param = arguments.id or arguments.userPrincipalName

        response = await self.query_disable_user(user_param, request_body, request_configuration)

        response.raise_for_status()


class EnableUserAction(MicrosoftGraphAction):
    name = "Enable User"
    description = (
        "Enable an Azure Active Directory user. Requires the User.ReadWrite.All app permission."  # noqa: E501
    )

    async def query_enable_user(self, user_param, req_body, req_conf):
        return await self.client.users.by_user_id(user_param).patch(body=req_body, request_configuration=req_conf)

    async def run(self, arguments: RequiredSingleUserArguments):
        request_body = User(account_enabled=True)
        request_configuration = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )
        user_param = arguments.id or arguments.userPrincipalName

        response = await self.query_enable_user(user_param, request_body, request_configuration)

        response.raise_for_status()


class ResetUserPasswordAction(MicrosoftGraphAction):
    name = "Reset User Password"
    description = "Reset a user's password. You will need UserAuthenticationMethod.ReadWrite.All deleguated permission."  # noqa: E501

    async def query_list_user_methods(self, user_param, req_conf):
        return await self.client.users.by_user_id(user_param).authentication.password_methods.get(
            request_configuration=req_conf
        )

    async def query_reset_user_password(self, user_param, id_methods, req_body, req_conf):
        return (
            await self.delegated_client.users.by_user_id(user_param)
            .authentication.methods.by_authentication_method_id(id_methods)
            .reset_password.post(body=req_body, request_configuration=req_conf)
        )

    async def run(self, arguments: RequiredTwoUserArguments):
        request_configuration = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )
        user_param = arguments.id or arguments.userPrincipalName

        response_listMethods = await self.query_list_user_methods(user_param, request_configuration)

        response_listMethods.raise_for_status()

        id_methods = response_listMethods.json().get("value")[0].get("id")
        request_body = ResetPasswordPostRequestBody(new_password=arguments.userNewPassword)

        response = await self.query_reset_user_password(user_param, id_methods, request_body, request_configuration)

        response.raise_for_status()
