"""Contains DisableUsersAction."""
from typing import Any

from loguru import logger
from pydantic import BaseModel
from sekoia_automation.action import Action

from actions import MicrosoftModule
from client.commands import PowershellCommand
from client.windows_client import WindowsRemoteClient


class DisableUsersActionConfig(BaseModel):
    """Config for DisableUsersAction."""

    users: list[str] | None
    sids: list[str] | None
    server: str


class DisableUsersAction(Action):
    """Action to disable users."""

    module: MicrosoftModule

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

        logger.info("Disabling users {0}", config.users)

        WindowsRemoteClient(
            config.server, self.module.configuration.username, self.module.configuration.password
        ).execute_command(command)

        logger.info("Users {0} disabled", config.users)

        return {}
