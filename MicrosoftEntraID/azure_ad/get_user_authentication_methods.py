from azure_ad.base import MicrosoftGraphAction

from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder


class GetUserAuthenticationMethodsAction(MicrosoftGraphAction):
    name = "Get User Authentication Methods"
    description = "Get information about an user's authentication methods (such as their MFA status). Requires the UserAuthenticationMethod.Read.All permission."  # noqa: E501
    # results_model doesn't support async model

    async def query_user_auth_methods(self, req_conf):
        return await self.client.reports.authentication_methods.user_registration_details.get(
            request_configuration=req_conf
        )

    async def run(self, arguments):
        query_params = None
        if arguments.get("userPrincipalName"):
            query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                filter=f"userPrincipalName eq '{arguments.get('userPrincipalName')}'"
            )

        request_configuration = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())], query_parameters=query_params
        )

        response = await self.query_user_auth_methods(request_configuration)
        response.raise_for_status()

        return {"authenticationResults": response.json().get("value")}
