"""Contains tests for WindowsRemoteClient."""
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker

from client.commands import PowershellCommand, PowershellCommandException
from client.windows_client import WindowsRemoteClient


@pytest.mark.asyncio
async def test_execute_command_success(mock_session: MagicMock, session_faker: Faker):
    """
    Test execute_command method of WindowsRemoteClient.

    Args:
        mock_session: MagicMock
        session_faker: Faker
    """
    # Mocking the Response object
    mock_response = MagicMock()
    mock_response.status_code = 0
    mock_session.return_value.run_cmd.return_value = mock_response

    # Mocking the compile method of PowershellCommand
    compiled_command = session_faker.pystr()
    arguments = [session_faker.word(), session_faker.word()]

    server = session_faker.word()
    username = session_faker.word()
    password = session_faker.word()

    with patch.object(PowershellCommand, "compile", return_value=(compiled_command, arguments)):
        client = WindowsRemoteClient(server, username, password)
        command = PowershellCommand(command=compiled_command, arguments=arguments)

        # Test execute_command method
        response = client.execute_command(command)

        # Assert that the Session and Response were called with the expected parameters
        mock_session.assert_called_once_with(server, auth=(username, password), transport="credssp")
        mock_session.return_value.run_cmd.assert_called_once_with(compiled_command, arguments)

        # Assert that the response is returned
        assert response == mock_response


@pytest.mark.asyncio
async def test_execute_command_failure(mock_session: MagicMock, session_faker: Faker):
    """
    Test execute_command method of WindowsRemoteClient when the command fails.

    Args:
        mock_session:
        session_faker:
    """
    mock_response = MagicMock()
    mock_response.status_code = 1  # Simulate a non-zero status code (indicating an error)
    mock_response.std_err = session_faker.pystr().encode("utf-8")  # Simulate an error message
    mock_session.return_value.run_cmd.return_value = mock_response

    # Mocking the compile method of PowershellCommand
    compiled_command = session_faker.pystr()
    arguments = [session_faker.word(), session_faker.word()]

    server = session_faker.word()
    username = session_faker.word()
    password = session_faker.word()
    with patch.object(PowershellCommand, "compile", return_value=(compiled_command, arguments)):
        client = WindowsRemoteClient(server, username, password)
        command = PowershellCommand(command=compiled_command, arguments=arguments)

        # Test execute_command method and ensure it raises PowershellCommandException
        with pytest.raises(PowershellCommandException):
            client.execute_command(command)

        # Assert that the Session and Response were called with the expected parameters
        mock_session.assert_called_once_with(server, auth=(username, password), transport="credssp")
        mock_session.return_value.run_cmd.assert_called_once_with(compiled_command, arguments)
