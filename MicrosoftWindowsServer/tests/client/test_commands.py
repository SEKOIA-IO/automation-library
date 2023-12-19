"""Test client commands."""
from base64 import b64encode

import pytest
from faker import Faker

from client.commands import PowershellCommand, PowershellCommandException


@pytest.mark.asyncio
async def test_powershell_command_init(session_faker: Faker):
    """
    Test PowershellCommand initialization.

    Args:
        session_faker: Faker
    """
    command = session_faker.pystr()
    arguments = [session_faker.pystr(), session_faker.pystr()]

    ps_command = PowershellCommand(command=command, arguments=arguments)

    assert ps_command._command == command
    assert ps_command._arguments == arguments

    cmd_list = [session_faker.word(), session_faker.word()]
    ps_command_2 = PowershellCommand(commands=cmd_list)
    assert ps_command_2._command == "\n".join(cmd_list)

    with pytest.raises(ValueError):
        PowershellCommand()


@pytest.mark.asyncio
async def test_powershell_command_compile(session_faker: Faker):
    """
    Test PowershellCommand compilation.

    Args:
        session_faker: Faker
    """
    command = session_faker.pystr()
    arguments = [session_faker.pystr(), session_faker.pystr()]

    ps_command = PowershellCommand(command=command, arguments=arguments)

    assert ps_command.compile() == (
        "powershell -encodedcommand {0}".format(b64encode(command.encode("utf_16_le")).decode("ascii")),
        arguments,
    )


@pytest.mark.asyncio
async def test_powershell_command_change_user_password(session_faker: Faker):
    """
    Test PowershellCommand change_user_password.

    Args:
        session_faker: Faker
    """
    username = session_faker.pystr()
    password = session_faker.pystr()

    commands = [
        '$Secure_String_Pwd = ConvertTo-SecureString "{0}" -AsPlainText -Force'.format(password),
        'Set-LocalUser -Password $Secure_String_Pwd -Name "{0}"'.format(username),
    ]

    ps_command = PowershellCommand.change_user_password(username=username, password=password)

    assert ps_command._command == "\n".join(commands)
    assert ps_command._arguments == []


@pytest.mark.asyncio
async def test_powershell_command_enable_users(session_faker: Faker):
    """
    Test PowershellCommand enable users.

    Args:
        session_faker: Faker
    """
    single_username = session_faker.word()
    single_sid = session_faker.word()
    usernames = [session_faker.word(), session_faker.word()]
    sids = [session_faker.word(), session_faker.word()]

    ps_command_1 = PowershellCommand.enable_users(usernames=usernames)
    assert ps_command_1._command == 'Enable-LocalUser -Name "{0}","{1}"'.format(usernames[0], usernames[1])
    assert ps_command_1._arguments == []

    ps_command_2 = PowershellCommand.enable_users(usernames=[single_username])
    assert ps_command_2._command == 'Enable-LocalUser -Name "{0}"'.format(single_username)
    assert ps_command_2._arguments == []

    ps_command_3 = PowershellCommand.enable_users(sids=sids)
    assert ps_command_3._command == 'Enable-LocalUser -SID "{0}","{1}"'.format(sids[0], sids[1])
    assert ps_command_3._arguments == []

    ps_command_4 = PowershellCommand.enable_users(sids=[single_sid])
    assert ps_command_4._command == 'Enable-LocalUser -SID "{0}"'.format(single_sid)
    assert ps_command_4._arguments == []

    with pytest.raises(ValueError):
        PowershellCommand.enable_users()


@pytest.mark.asyncio
async def test_powershell_command_disable_users(session_faker: Faker):
    """
    Test PowershellCommand disable users.

    Args:
        session_faker: Faker
    """
    single_username = session_faker.word()
    single_sid = session_faker.word()
    usernames = [session_faker.word(), session_faker.word()]
    sids = [session_faker.word(), session_faker.word()]

    ps_command_1 = PowershellCommand.disable_users(usernames=usernames)
    assert ps_command_1._command == 'Disable-LocalUser -Name "{0}","{1}"'.format(usernames[0], usernames[1])
    assert ps_command_1._arguments == []

    ps_command_2 = PowershellCommand.disable_users(usernames=[single_username])
    assert ps_command_2._command == 'Disable-LocalUser -Name "{0}"'.format(single_username)
    assert ps_command_2._arguments == []

    ps_command_3 = PowershellCommand.disable_users(sids=sids)
    assert ps_command_3._command == 'Disable-LocalUser -SID "{0}","{1}"'.format(sids[0], sids[1])
    assert ps_command_3._arguments == []

    ps_command_4 = PowershellCommand.disable_users(sids=[single_sid])
    assert ps_command_4._command == 'Disable-LocalUser -SID "{0}"'.format(single_sid)
    assert ps_command_4._arguments == []

    with pytest.raises(ValueError):
        PowershellCommand.disable_users()


@pytest.mark.asyncio
async def test_powershell_command_exception(session_faker: Faker):
    """
    Test PowershellCommand exception.

    Args:
        session_faker: Faker
    """
    error_message = session_faker.pystr()
    command = session_faker.pystr()

    exception = PowershellCommandException(error=error_message, command=PowershellCommand(command))
    expected_message = "Error message: {error_message}\n{command}".format(
        error_message=error_message, command=PowershellCommand(command)
    )

    assert str(exception) == expected_message
