from pydantic import BaseModel

from .base import MicrosoftGraphAction, RequiredSingleUserArguments


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
    description = "Get information about an Azure Active Directory user. Requires the User.Read.All permission."
    results_model = GetUserResults

    def run(self, arguments: RequiredSingleUserArguments):
        response = self.client.get(
            f"/users/{arguments.id or arguments.userPrincipalName}",
            params={"$select": ",".join(GetUserResults.schema()["properties"].keys())},
        )

        response.raise_for_status()

        return response.json()


class DisableUserAction(MicrosoftGraphAction):
    name = "Disable User"
    description = "Disable an Azure Active Directory user. Requires the User.ReadWrite.All permission."

    def run(self, arguments: RequiredSingleUserArguments):
        self.client.patch(
            f"/users/{arguments.id or arguments.userPrincipalName}",
            json={"accountEnabled": False},
        ).raise_for_status()


class EnableUserAction(MicrosoftGraphAction):
    name = "Enable User"
    description = "Enable an Azure Active Directory user. Requires the User.ReadWrite.All permission."

    def run(self, arguments: RequiredSingleUserArguments):
        self.client.patch(
            f"/users/{arguments.id or arguments.userPrincipalName}",
            json={"accountEnabled": True},
        ).raise_for_status()
