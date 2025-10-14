from typing import Any

from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph.generated.models.user_registration_details_collection_response import (
    UserRegistrationDetailsCollectionResponse,
)
from msgraph.generated.reports.authentication_methods.user_registration_details.user_registration_details_request_builder import (
    UserRegistrationDetailsRequestBuilder,
)

from azure_ad.base import MicrosoftGraphAction
from graph_api.client import GraphApi


class GetUserAuthenticationMethodsAction(MicrosoftGraphAction):
    name = "Get User Authentication Methods"
    description = "Get information about an user's authentication methods (such as their MFA status). Requires the UserAuthenticationMethod.Read.All permission."  # noqa: E501
    # results_model doesn't support async model

    async def query_user_auth_methods(
        self,
        req_conf: RequestConfiguration[
            UserRegistrationDetailsRequestBuilder.UserRegistrationDetailsRequestBuilderGetQueryParameters
        ],
    ) -> UserRegistrationDetailsCollectionResponse | None: # pragma: no cover
        return await self.client.reports.authentication_methods.user_registration_details.get(
            request_configuration=req_conf
        )

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query_params = None
        if arguments.get("userPrincipalName"):
            query_params = (
                UserRegistrationDetailsRequestBuilder.UserRegistrationDetailsRequestBuilderGetQueryParameters(
                    filter=f"userPrincipalName eq '{arguments.get('userPrincipalName')}'"
                )
            )

        request_configuration = RequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())], query_parameters=query_params
        )

        response = await self.query_user_auth_methods(request_configuration)
        if response is None:
            raise ValueError("No response received from the server for Get User Authentication Methods action.")

        return GraphApi.encode_values_as_dict("authenticationResults", response.value or [])
