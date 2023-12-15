"""Contains the EnableUsersAction."""
from typing import Any

from pydantic import BaseModel
from sekoia_automation.action import Action

from actions import MicrosoftModule
from client.commands import PowershellCommand
from client.windows_client import WindowsRemoteClient


class EnableUsersActionConfig(BaseModel):
    """Config for EnableUsersAction."""

    users: list[str] | None
    sids: list[str] | None


class EnableUsersAction(Action):
    """Action to enable users."""

    module: MicrosoftModule

    def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Run the action.

        Args:
            arguments: dict[str, Any]

        Returns:
            dict:
        """
        config = EnableUsersActionConfig(**arguments)
        command = PowershellCommand.enable_users(usernames=config.users, sids=config.sids)

        WindowsRemoteClient(
            self.module.configuration.server, self.module.configuration.username, self.module.configuration.password
        ).execute_command(command)

        return {}
