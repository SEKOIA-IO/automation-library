"""Contains custom commands and exception representation for the Microsoft module."""

from base64 import b64encode
from typing import Any, Tuple


class PowershellCommand(object):
    """A Powershell command representation."""

    def __init__(
        self, command: str | None = None, commands: list[str] | None = None, arguments: list[Any] | None = None
    ) -> None:
        """
        Initialize a Powershell command.

        If both command and commands are provided, command will be used.

        Args:
            command: str | None
            commands: list[str] | None
            arguments: list[str] | None
        """
        if not command and not commands:
            raise ValueError("Either command or commands must be provided.")

        self._command = command or "\n".join(commands or [])
        self._arguments = arguments or []

    def compile(self) -> Tuple[str, list[Any]]:
        """
        Compile a Powershell command.

        Returns:
            Tuple[str, list[Any]]:
        """
        encoded_ps = b64encode(self._command.encode("utf_16_le")).decode("ascii")

        return "powershell -encodedcommand {0}".format(encoded_ps), self._arguments

    def __str__(self) -> str:
        """
        Get a string representation of a Powershell command.

        Returns:
            str:
        """
        return "Command: {command} | Arguments: {arguments}".format(
            command=self._command, arguments=" ".join(self._arguments)
        )

    @staticmethod
    def change_user_password(username: str, password: str) -> "PowershellCommand":
        """
        Change user password.

        Args:
            username: str
            password: str

        Returns:
            PowershellCommand:
        """
        return PowershellCommand(
            commands=[
                '$Secure_String_Pwd = ConvertTo-SecureString "{0}" -AsPlainText -Force'.format(password),
                'Set-LocalUser -Password $Secure_String_Pwd -Name "{0}"'.format(username),
            ]
        )

    @staticmethod
    def enable_users(usernames: list[str] | None = None, sids: list[str] | None = None) -> "PowershellCommand":
        """
        Enable local user.

        Args:
            usernames: list[str] | None
            sids: list[str] | None

        Returns:
            PowershellCommand:
        """
        if usernames:
            values = ['"{0}"'.format(username) for username in usernames]
            command = "Enable-LocalUser -Name {0}".format(",".join(values))

        elif sids:
            values = ['"{0}"'.format(sid) for sid in sids]
            command = "Enable-LocalUser -SID {0}".format(",".join(values))

        else:
            raise ValueError("Either usernames or sids must be provided.")

        return PowershellCommand(command=command)

    @staticmethod
    def disable_users(usernames: list[str] | None = None, sids: list[str] | None = None) -> "PowershellCommand":
        """
        Disable local user.

        Args:
            usernames: list[str] | None
            sids: list[str] | None

        Returns:
            PowershellCommand:
        """
        if usernames:
            values = ['"{0}"'.format(username) for username in usernames]
            command = "Disable-LocalUser -Name {0}".format(",".join(values))

        elif sids:
            values = ['"{0}"'.format(sid) for sid in sids]
            command = "Disable-LocalUser -SID {0}".format(",".join(values))

        else:
            raise ValueError("Either usernames or sids must be provided.")

        return PowershellCommand(command=command)


class PowershellCommandException(Exception):
    """A Powershell command exception."""

    def __init__(self, error: str, command: PowershellCommand) -> None:
        """
        Initialize a Powershell command exception.

        Args:
            error: str
            command: PowershellCommand
        """
        self.error = error
        self.command = command

    def __str__(self) -> str:
        """
        Get a string representation of a PowershellCommandException exception.

        Returns:
            str:
        """
        return """Error message: {error}\n{source}""".format(error=self.error, source=self.command)
