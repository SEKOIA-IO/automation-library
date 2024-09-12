from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder
from pydantic import BaseModel

from .base import MicrosoftGraphAction, RequiredSingleUserArguments


class GetUserAuthenticationMethodsResults(BaseModel):
    id: str
    userPrincipalName: str
    userDisplayName: str | None
    isSsprRegistered: bool
    isSsprEnabled: bool
    isSsprCapable: bool
    isMfaRegistered: bool
    isMfaCapable: bool
    isPasswordlessCapable: bool
    methodsRegistered: list[str] | None
    defaultMfaMethod: str | None


class GetUserAuthenticationMethodsAction(MicrosoftGraphAction):
    name = "Get User Authentication Methods"
    description = "Get information about an user's authentication methods (such as their MFA status). Requires the UserAuthenticationMethod.Read.All permission."  # noqa: E501
    # results_model = GetUserAuthenticationMethodsResults

    async def query_user_auth_methods(self, req_conf):
        return await self.client.reports.authentication_methods.user_registration_details.get(
            request_configuration=req_conf
        )

    async def run(self, arguments: RequiredSingleUserArguments):
        query_params = None

        if arguments.id:
            query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                filter=f"id eq '{arguments.id}'"
            )

        elif arguments.userPrincipalName:
            query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                filter=f"userPrincipalName eq '{arguments.userPrincipalName}'"
            )

        if not query_params:
            raise ValueError("Either 'id' or 'userPrincipalName' must be provided.")

        request_configuration = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())], query_parameters=query_params
        )

        response = await self.query_user_auth_methods(request_configuration)

        response.raise_for_status()

        return response.json()["value"][0]
