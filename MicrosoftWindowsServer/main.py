"""Module to work with windows remote server."""

from actions import MicrosoftModule
from actions.change_user_password_action import ChangeUserPasswordAction
from actions.disable_users_action import DisableUsersAction
from actions.enable_users_action import EnableUsersAction

if __name__ == "__main__":
    module = MicrosoftModule()

    module.register(ChangeUserPasswordAction, "change-user-password")
    module.register(EnableUsersAction, "enable-users")
    module.register(DisableUsersAction, "disable-users")

    module.run()
