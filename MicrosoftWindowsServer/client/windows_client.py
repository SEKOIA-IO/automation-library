"""WinRM client to work with remote Windows machine."""

from functools import cached_property

from loguru import logger
from winrm import Response, Session

from .commands import PowershellCommand, PowershellCommandException


class WindowsRemoteClient(object):
    """A client to work with remote Windows machine."""

    def __init__(self, server: str, username: str, password: str) -> None:
        """
        Initialize a client to work with remote Windows machine.

        Args:
            server: str
            username: str
            password: str
        """
        self.server = server
        self.username = username
        self.password = password

    @cached_property
    def _session(self) -> Session:
        """
        Create a client to interact with remote server.

        Returns:
            Session:
        """
        return Session(self.server, auth=(self.username, self.password), transport="credssp")

    def execute_command(self, command: PowershellCommand) -> Response:
        """
        Execute a command on the remote server.

        Args:
            command: PowershellCommand

        Returns:
            Response:
        """
        logger.info("Start to execute command on remote server")
        compiled_command, arguments = command.compile()

        response = self._session.run_cmd(compiled_command, arguments)

        if int(response.status_code) != 0:
            raise PowershellCommandException(bytes(response.std_err).decode("utf-8"), command)

        return response
