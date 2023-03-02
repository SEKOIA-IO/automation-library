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
    results_model = GetUserAuthenticationMethodsResults

    def run(self, arguments: RequiredSingleUserArguments):
        params = {}

        if arguments.id:
            params["$filter"] = f"id eq '{arguments.id}'"
        else:
            params["$filter"] = f"userPrincipalName eq '{arguments.userPrincipalName}'"

        response = self.client.get(
            "/reports/authenticationMethods/userRegistrationDetails/",
            params=params,
        )
        response.raise_for_status()

        return response.json()["value"][0]
