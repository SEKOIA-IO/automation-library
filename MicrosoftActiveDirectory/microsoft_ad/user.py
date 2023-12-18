from .base import MicrosoftADAction, ResetPassUserArguments, UserAccountArguments


class ResetUserPasswordAction(MicrosoftADAction):
    name = "Reset Password"
    description = "Reset password with an rdp connection with an admin account"

    def run(self, arguments: ResetPassUserArguments):
        user_query = self.search_userdn_query(arguments.username, arguments.basedn)

        if len(user_query) == 0:
            raise Exception(f"There's no one with this name !!")

        if len(user_query) > 1:
            raise Exception(f"There's {len(user_query)} persons with the same name !!")

        try:
            user_dn = user_query[0][0]
            self.client.extend.microsoft.modify_password(user_dn, arguments.new_password)

            if self.client.result.get("description") != "success":
                raise Exception(f"Reset password action failed : {self.client.result.get('description')}")
        except:
            raise Exception(f"Failed to reset {arguments.username} password account!!!")


class EnableUserAction(MicrosoftADAction):
    name = "Enable User"
    description = "Enable an Azure Active Directory user"

    def run(self, arguments: UserAccountArguments):
        user_query = self.search_userdn_query(arguments.username, arguments.basedn)

        if len(user_query) == 0:
            raise Exception(f"There's no one with this name !!")

        if len(user_query) > 1:
            raise Exception(f"There's {len(user_query)} persons with the same name !!")

        try:
            userADAccountControlFlag = 2
            user_dn = user_query[0][0]
            userAccountControl = user_query[0][1] & ~userADAccountControlFlag
            self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", (userAccountControl))]}, None)

            if self.client.result.get("description") != "success":
                raise Exception(f"Enable action failed : {self.client.result.get('description')}")
        except:
            raise Exception(f"Failed to Enable {arguments.username} account!!!")


class DisableUserAction(MicrosoftADAction):
    name = "Disable User"
    description = "Disable an Azure Active Directory user"

    def run(self, arguments: UserAccountArguments):
        user_query = self.search_userdn_query(arguments.username, arguments.basedn)

        if len(user_query) == 0:
            raise Exception(f"There's no one with this name !!")

        if len(user_query) > 1:
            raise Exception(f"There's {len(user_query)} persons with the same name !!")

        try:
            userADAccountControlFlag = 2
            user_dn = user_query[0][0]
            userAccountControl = user_query[0][1] | userADAccountControlFlag
            self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", (userAccountControl))]}, None)

            if self.client.result.get("description") != "success":
                raise Exception(f"Disable action failed : {self.client.result.get('description')}")

        except:
            raise Exception(f"Failed to Disable {arguments.username} account!!!")
