from .base import MicrosoftADAction, ResetPassUserArguments, UserAccountArguments


class ResetUserPasswordAction(MicrosoftADAction):
    name = "Reset Password"
    description = "Reset password with an rdp connection with an admin account"

    def run(self, arguments: ResetPassUserArguments):
        users_dn = self.search_userdn_query(arguments.username, arguments.basedn)

        if len(users_dn) == 0:
            raise Exception(f"There's no one with this name !!")

        if len(users_dn) > 1:
            raise Exception(f"There's {len(users_dn)} persons with the same name !!")

        try:
            self.client.extend.microsoft.modify_password(users_dn[0], arguments.new_password)
        except:
            self.log(f"Failed to reset {arguments.username} password account!!!")


class EnableUserAction(MicrosoftADAction):
    name = "Enable User"
    description = "Enable an Azure Active Directory user"

    def run(self, arguments: UserAccountArguments):
        users_dn = self.search_userdn_query(arguments.username, arguments.basedn)

        if len(users_dn) == 0:
            raise Exception(f"There's no one with this name !!")

        if len(users_dn) > 1:
            raise Exception(f"There's {len(users_dn)} persons with the same name !!")

        try:
            self.client.modify(users_dn[0], {"userAccountControl": [("MODIFY_REPLACE", (512))]}, None)
        except:
            self.log(f"Failed to Enable {arguments.username} account!!!")


class DisableUserAction(MicrosoftADAction):
    name = "Disable User"
    description = "Disable an Azure Active Directory user"

    def run(self, arguments: UserAccountArguments):
        users_dn = self.search_userdn_query(arguments.username, arguments.basedn)

        if len(users_dn) == 0:
            raise Exception(f"There's no one with this name !!")

        if len(users_dn) > 1:
            raise Exception(f"There's {len(users_dn)} persons with the same name !!")

        try:
            self.client.modify(users_dn[0], {"userAccountControl": [("MODIFY_REPLACE", (514))]}, None)
        except:
            self.log(f"Failed to Disable {arguments.username} account!!!")
