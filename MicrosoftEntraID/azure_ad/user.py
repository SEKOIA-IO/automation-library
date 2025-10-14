from typing import Any

from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_abstractions.default_query_parameters import QueryParameters
from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph.generated.models.password_authentication_method_collection_response import (
    PasswordAuthenticationMethodCollectionResponse,
)
from msgraph.generated.models.password_reset_response import PasswordResetResponse
from msgraph.generated.models.user import User
from msgraph.generated.users.item.authentication.methods.item.reset_password.reset_password_post_request_body import (
    ResetPasswordPostRequestBody,
)
from msgraph.generated.users.item.authentication.password_methods.password_methods_request_builder import (
    PasswordMethodsRequestBuilder,
)
from msgraph.generated.users.item.user_item_request_builder import UserItemRequestBuilder
from pydantic.v1 import BaseModel

from graph_api.client import GraphApi

from .base import MicrosoftGraphAction, RequiredSingleUserArguments, RequiredTwoUserArguments


class GetUserResults(BaseModel):
    id: str | None
    accountEnabled: bool
    assignedLicenses: list[Any] | None
    city: str | None
    companyName: str | None
    country: str | None
    createdDateTime: str | None
    creationType: str | None
    deletedDateTime: str | None
    department: str | None
    displayName: str | None
    identities: list[Any] | None
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

    async def query_get_user(
        self,
        user_id: str,
        req_conf: RequestConfiguration[UserItemRequestBuilder.UserItemRequestBuilderGetQueryParameters],
    ) -> User | None:  # pragma: no cover
        return await self.client.users.by_user_id(user_id).get(request_configuration=req_conf)

    async def run(self, arguments: RequiredSingleUserArguments) -> dict[str, Any]:
        query_params = UserItemRequestBuilder.UserItemRequestBuilderGetQueryParameters(
            # select requires a list of strings, so we need to convert the keys of the schema to a list
            select=list(GetUserResults.schema()["properties"].keys()),
        )

        request_configuration = RequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())], query_parameters=query_params
        )

        response = await self.query_get_user(arguments.get_user_id(), request_configuration)

        if response is None:
            raise ValueError("No response received from the server for Get User action.")

        return GraphApi.encode_value_as_dict(response)


class DisableUserAction(MicrosoftGraphAction):
    name = "Disable User"
    description = (
        "Disable an Azure Active Directory user. Requires the User.ReadWrite.All app permission."  # noqa: E501
    )

    async def query_disable_user(
        self, user_id: str, req_body: User, req_conf: RequestConfiguration[QueryParameters]
    ) -> User | None:  # pragma: no cover
        return await self.client.users.by_user_id(user_id).patch(body=req_body, request_configuration=req_conf)

    async def run(self, arguments: RequiredSingleUserArguments) -> None:
        request_body = User(account_enabled=False)

        request_configuration: RequestConfiguration[QueryParameters] = RequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )

        response = await self.query_disable_user(arguments.get_user_id(), request_body, request_configuration)
        if response is None:
            raise ValueError("No response received from the server for Disable User action.")


class EnableUserAction(MicrosoftGraphAction):
    name = "Enable User"
    description = (
        "Enable an Azure Active Directory user. Requires the User.ReadWrite.All app permission."  # noqa: E501
    )

    async def query_enable_user(
        self, user_id: str, req_body: User, req_conf: RequestConfiguration[QueryParameters]
    ) -> User | None:  # pragma: no cover
        return await self.client.users.by_user_id(user_id).patch(body=req_body, request_configuration=req_conf)

    async def run(self, arguments: RequiredSingleUserArguments) -> None:
        request_body = User(account_enabled=True)
        request_configuration: RequestConfiguration[QueryParameters] = RequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )

        response = await self.query_enable_user(arguments.get_user_id(), request_body, request_configuration)
        if response is None:
            raise ValueError("No response received from the server for Enable User action.")


class ResetUserPasswordAction(MicrosoftGraphAction):
    name = "Reset User Password"
    description = "Reset a user's password. You will need UserAuthenticationMethod.ReadWrite.All deleguated permission."  # noqa: E501

    async def query_list_user_methods(
        self,
        user_id: str,
        req_conf: RequestConfiguration[PasswordMethodsRequestBuilder.PasswordMethodsRequestBuilderGetQueryParameters],
    ) -> PasswordAuthenticationMethodCollectionResponse | None:  # pragma: no cover
        return await self.client.users.by_user_id(user_id).authentication.password_methods.get(
            request_configuration=req_conf
        )

    async def query_reset_user_password(
        self,
        user_id: str,
        authentication_method_id: str,
        req_body: ResetPasswordPostRequestBody,
        req_conf: RequestConfiguration[QueryParameters],
    ) -> PasswordResetResponse | None:  # pragma: no cover
        return (
            await self.delegated_client.users.by_user_id(user_id)
            .authentication.methods.by_authentication_method_id(authentication_method_id)
            .reset_password.post(body=req_body, request_configuration=req_conf)
        )

    async def run(self, arguments: RequiredTwoUserArguments) -> None:
        list_user_methods_req_config: RequestConfiguration[
            PasswordMethodsRequestBuilder.PasswordMethodsRequestBuilderGetQueryParameters
        ] = RequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )

        user_id = arguments.get_user_id()

        methods_result = await self.query_list_user_methods(user_id, list_user_methods_req_config)
        if methods_result is None:
            raise ValueError("No response received from the server for listing user authentication methods.")

        methods_value = methods_result.value or []
        if len(methods_value) < 1:
            raise ValueError("The user has no password authentication methods to reset the password for.")

        id_methods = methods_value[0].id
        if not id_methods:
            raise ValueError("The user has no valid password authentication method ID.")

        request_body = ResetPasswordPostRequestBody(new_password=arguments.userNewPassword)
        reset_user_password_req_config: RequestConfiguration[QueryParameters] = RequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )

        result = await self.query_reset_user_password(
            user_id, id_methods, request_body, reset_user_password_req_config
        )
        if result is None:
            raise ValueError("No response received from the server for Reset User Password action.")
