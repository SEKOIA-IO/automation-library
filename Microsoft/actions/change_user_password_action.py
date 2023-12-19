"""Contains ChangeUserPasswordAction."""
from typing import Any

from pydantic import BaseModel
from sekoia_automation.action import Action

from actions import MicrosoftModule
from client.commands import PowershellCommand
from client.windows_client import WindowsRemoteClient


class ChangeUserPasswordActionConfig(BaseModel):
    """Config for ChangeUserPasswordAction."""

    user_to_update: str
    new_password: str


class ChangeUserPasswordAction(Action):
    """Action to change user password."""

    module: MicrosoftModule

    def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Run the action.

        Args:
            arguments: dict[str, Any]

        Returns:
            dict:
        """
        config = ChangeUserPasswordActionConfig(**arguments)
        command = PowershellCommand.change_user_password(config.user_to_update, config.new_password)

        WindowsRemoteClient(
            self.module.configuration.server, self.module.configuration.username, self.module.configuration.password
        ).execute_command(command)

        return {}
