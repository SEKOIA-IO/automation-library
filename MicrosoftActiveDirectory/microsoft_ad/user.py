from .base import MicrosoftADAction, ResetPassUserArguments, UserAccountArguments


class ResetUserPasswordAction(MicrosoftADAction):
    name = "Reset Password"
    description = "Reset password with an rdp connection with an admin account"

    def run(self, arguments: ResetPassUserArguments):
        user_dn = self.search_userdn_query(arguments.username, arguments.basedn)
        response = self.client.extend.microsoft.modify_password(user_dn, arguments.new_password)

        if not response:
            raise Exception(f"Failed to reset {arguments.username} password account!!!")


class EnableUserAction(MicrosoftADAction):
    name = "Enable User"
    description = "Enable an Azure Active Directory user"

    def run(self, arguments: UserAccountArguments):
        user_dn = self.search_userdn_query(arguments.username, arguments.basedn)
        response = self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", (512))]}, None)

        if not response:
            raise Exception(f"Failed to Enable {arguments.username} account!!!")


class DisableUserAction(MicrosoftADAction):
    name = "Disable User"
    description = "Disable an Azure Active Directory user"

    def run(self, arguments: UserAccountArguments):
        user_dn = self.search_userdn_query(arguments.username, arguments.basedn)
        response = self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", (514))]}, None)

        if not response:
            raise Exception(f"Failed to Disable {arguments.username} account!!!")
