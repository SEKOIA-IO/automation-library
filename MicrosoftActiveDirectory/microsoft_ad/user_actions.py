from ldap3.core.exceptions import LDAPException

from microsoft_ad.actions_base import MicrosoftADAction
from microsoft_ad.models.action_models import ResetPassUserArguments, UserAccountArguments


DEFAULT_UAC = 512


class ResetUserPasswordAction(MicrosoftADAction):
    name = "Reset Password"
    description = "Reset password with an rdp connection with an admin account"

    def run(self, arguments: ResetPassUserArguments):
        self.log(f"Starting password reset for user: {arguments.username}", level="info")

        user_query = self.search_userdn_query(arguments.username, arguments.basedn)

        if len(user_query) == 0:
            raise Exception(f"User not found: {arguments.username}")

        if len(user_query) > 1:
            raise Exception(f"Multiple users found with name: {arguments.username}, count: {len(user_query)}")

        try:
            user_dn = user_query[0][0]
            self.client.extend.microsoft.modify_password(user_dn, arguments.new_password)

            if self.client.result.get("description") != "success":
                raise Exception(
                    f"Password reset failed for {arguments.username} : {self.client.result.get('description')}"
                )

            self.log(f"Password reset successful for user: {arguments.username}", level="info")

        except LDAPException as e:
            raise Exception(f"Failed to reset {arguments.username} password account: {e}") from e


class EnableUserAction(MicrosoftADAction):
    name = "Enable User"
    description = "Enable an Azure Active Directory user"

    def run(self, arguments: UserAccountArguments):
        user_query = self.search_userdn_query(arguments.username, arguments.basedn)

        if len(user_query) == 0:
            raise Exception(f"User not found: {arguments.username}")

        if len(user_query) > 1:
            raise Exception(f"Multiple users found with name: {arguments.username}, count: {len(user_query)}")

        try:
            uac_disabled = 2
            user_dn = user_query[0][0]
            current_uac = user_query[0][1] if user_query[0][1] is not None else DEFAULT_UAC

            self.log(f"User DN : {user_dn} and userAccountControl value {current_uac} were found", level="info")

            new_uac = current_uac & ~uac_disabled
            self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", new_uac)]}, None)

            if self.client.result.get("description") != "success":
                raise Exception(
                    f"Enable action failed for {arguments.username}: {self.client.result.get('description')}"
                )

            self.log(f"User {arguments.username} enabled successfully", level="info")

        except LDAPException as e:
            raise Exception(f"Failed to Enable {arguments.username} account: {e}") from e


class DisableUserAction(MicrosoftADAction):
    name = "Disable User"
    description = "Disable an Azure Active Directory user"

    def run(self, arguments: UserAccountArguments):
        self.log(f"Starting disable action for user: {arguments.username}", level="info")

        user_query = self.search_userdn_query(arguments.username, arguments.basedn)

        if len(user_query) == 0:
            raise Exception(f"User not found: {arguments.username}")

        if len(user_query) > 1:
            raise Exception(f"Multiple users found with name: {arguments.username}, count: {len(user_query)}")

        try:
            uac_disabled = 2
            user_dn = user_query[0][0]
            current_uac = user_query[0][1] if user_query[0][1] is not None else DEFAULT_UAC

            self.log(f"User DN : {user_dn} and userAccountControl value {current_uac} were found", level="info")

            new_uac = current_uac | uac_disabled

            self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", new_uac)]}, None)

            if self.client.result.get("description") != "success":
                raise Exception(
                    f"Disable action failed for {arguments.username}: {self.client.result.get('description')}"
                )

            self.log(f"User {arguments.username} has been disabled successfully", level="info")

        except LDAPException as e:
            raise Exception(f"Failed to Disable {arguments.username} account: {e}") from e
