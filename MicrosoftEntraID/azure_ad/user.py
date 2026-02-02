import secrets
import string
from functools import cached_property

from azure.identity import UsernamePasswordCredential
from azure.identity.aio import ClientSecretCredential
from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph import GraphServiceClient
from msgraph.generated.models.password_profile import PasswordProfile
from msgraph.generated.models.user import User
from msgraph.generated.users.item.authentication.methods.item.reset_password.reset_password_post_request_body import (
    ResetPasswordPostRequestBody,
)
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder
from pydantic.v1 import BaseModel

from .base import (
    MicrosoftGraphAction,
    RequiredSingleUserArguments,
    RequiredTwoUserArguments,
    RequiredTwoUserArgumentsV2,
)


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
    name = "Reset User Password [DEPRECATED]"
    description = "Reset a user's password. You will need UserAuthenticationMethod.ReadWrite. All deleguated permission."  # noqa: E501

    async def query_list_user_methods(self, user_param, req_conf):
        return await self.client.users.by_user_id(user_param).authentication.password_methods.get(
            request_configuration=req_conf
        )

    @cached_property
    def client(self):
        """
        Used client with preconfigured scopes for password reset action
        It's a not a good practice to use. But the app permission not supported for this action
        More information about it here:
        https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.usernamepasswordcredential?view=azure-python
        """
        credentials = UsernamePasswordCredential(
            client_id=self.module.configuration.client_id,
            username=self.module.configuration.username,
            password=self.module.configuration.password,
            tenant_id=self.module.configuration.tenant_id,
        )

        # https://learn.microsoft.com/en-us/graph/authenticationmethods-get-started
        # Put scopes explicitly in order to follow documentation and avoid issues
        scopes = ["UserAuthenticationMethod.ReadWrite.All"]

        return GraphServiceClient(credentials=credentials, scopes=scopes)

    async def query_reset_user_password(self, user_param, id_methods, req_body, req_conf):
        return (
            await self.client.users.by_user_id(user_param)
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


PASSWORD_DEFAULT_LENGTH: int = 10  # Min length based on docs is 8
PASSWORD_MIN_LOWER: int = 1
PASSWORD_MIN_UPPER: int = 1
PASSWORD_MIN_DIGITS: int = 1
PASSWORD_MIN_SPECIALS: int = 1
PASSWORD_SPECIALS: str = "!@#$%^&*()-_=+[]{}:,.?"


class ResetUserPasswordActionV2(MicrosoftGraphAction):
    name = "Reset User Password Through Patching Password Profile"
    description = (
        "Resets a user's password by patching passwordProfile. "
        "Requires User-PasswordProfile.ReadWrite.All (Application), admin consent "
        "and appropriate Entra role assignment."
    )

    @cached_property
    def client(self) -> GraphServiceClient:
        """
        Recommended is ClientSecretCredential. Switch here to it instead of UsernamePasswordCredential
        But the same permissions ReadWrite are still required
        More info here: https://learn.microsoft.com/en-us/graph/api/user-update?view=graph-rest-1.0&tabs=http
        """
        credential = ClientSecretCredential(
            tenant_id=self.module.configuration.tenant_id,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )

        # For application permissions, we should use .default
        scopes = ["https://graph.microsoft.com/.default"]

        return GraphServiceClient(credentials=credential, scopes=scopes)

    async def query_reset_user_password(
        self,
        user_id_or_upn: str,
        new_password: str,
        force_change_password_next_sign_in: bool,
        force_change_password_next_sign_in_with_mfa: bool | None = None,
    ):
        password_profile = PasswordProfile(
            password=new_password,
            force_change_password_next_sign_in=force_change_password_next_sign_in,
        )

        if force_change_password_next_sign_in and force_change_password_next_sign_in_with_mfa:
            # https://learn.microsoft.com/en-us/graph/api/resources/passwordprofile?view=graph-rest-1.0
            password_profile = PasswordProfile(
                password=new_password,
                force_change_password_next_sign_in=force_change_password_next_sign_in,
                force_change_password_next_sign_in_with_mfa=True,
            )

        body = User(password_profile=password_profile)

        # Graph API can return the updated resource with `Prefer` header
        # Otherwise PATCH will return 204 No Content. For now it is ok but check later
        #
        # request_config: RequestConfiguration[QueryParameters] = RequestConfiguration(
        #     options=[ResponseHandlerOption(NativeResponseHandler())],
        # )
        # request_config.headers.add("Prefer", "return=representation")

        # Without NativeResponseHandler it will raise APIError in case of error
        # No need to reraise again with raise_for_status
        await self.client.users.by_user_id(user_id_or_upn).patch(
            body=body,
            request_configuration=RequestConfiguration(),
        )

    async def run(self, arguments: RequiredTwoUserArgumentsV2) -> dict[str, str]:
        new_password = (arguments.userNewPassword or "").strip()
        if not new_password:
            new_password = self.generate_password()

        user_id_or_upn = (arguments.id or arguments.userPrincipalName or "").strip()
        if not user_id_or_upn:
            raise ValueError("User id or principal name is required for this operation.")

        await self.query_reset_user_password(
            user_id_or_upn=user_id_or_upn,
            new_password=new_password,
            force_change_password_next_sign_in=arguments.forceChangePasswordNextSignIn,
            force_change_password_next_sign_in_with_mfa=arguments.forceChangePasswordNextSignInWithMfa,
        )

        return {
            "newPassword": new_password,
        }

    @staticmethod
    def generate_password() -> str:
        """
        Generates a password that satisfies common Entra password policies:
        - at least one lower, upper, digit, special
        - reasonable default length (20)

        https://learn.microsoft.com/en-us/entra/identity/authentication/concept-password-ban-bad-combined-policy
        """
        rng = secrets.SystemRandom()

        lower = [rng.choice(string.ascii_lowercase) for _ in range(PASSWORD_MIN_LOWER)]
        upper = [rng.choice(string.ascii_uppercase) for _ in range(PASSWORD_MIN_UPPER)]
        digits = [rng.choice(string.digits) for _ in range(PASSWORD_MIN_DIGITS)]
        special = [rng.choice(PASSWORD_SPECIALS) for _ in range(PASSWORD_MIN_SPECIALS)]

        remaining_len = PASSWORD_DEFAULT_LENGTH - (
            PASSWORD_MIN_LOWER + PASSWORD_MIN_UPPER + PASSWORD_MIN_DIGITS + PASSWORD_MIN_SPECIALS
        )
        alphabet = string.ascii_letters + string.digits + PASSWORD_SPECIALS
        remaining = [rng.choice(alphabet) for _ in range(remaining_len)]

        password_chars = lower + upper + digits + special + remaining
        rng.shuffle(password_chars)

        return "".join(password_chars)
