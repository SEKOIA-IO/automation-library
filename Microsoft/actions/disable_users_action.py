"""Contains DisableUsersAction."""
from typing import Any

from pydantic import BaseModel
from sekoia_automation.action import Action

from client.commands import PowershellCommand
from client.windows_client import WindowsRemoteClient


class DisableUsersActionConfig(BaseModel):
    """Config for DisableUsersAction."""

    username: str
    password: str
    server: str
    users: list[str] | None
    sids: list[str] | None


class DisableUsersAction(Action):
    """Action to disable users."""

    def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Run the action.

        Args:
            arguments: dict[str, Any]

        Returns:
            dict:
        """
        config = DisableUsersActionConfig(**arguments)
        command = PowershellCommand.disable_users(usernames=config.users, sids=config.sids)

        WindowsRemoteClient(config.server, config.username, config.password).execute_command(command)

        return {}
