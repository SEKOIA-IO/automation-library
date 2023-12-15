"""Tests for DisableUsersAction."""
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from faker import Faker
from pydantic import ValidationError

from actions.disable_users_action import DisableUsersAction
from client.commands import PowershellCommand


@pytest.mark.asyncio
async def test_disable_users_action_run_success(
    symphony_storage: Path,
    mock_session: MagicMock,
    session_faker: Faker,
):
    """
    Test run method of DisableUsersAction.

    Args:
        symphony_storage: Path
        mock_session: MagicMock
        session_faker: Faker
    """
    mock_response = MagicMock()
    mock_response.status_code = 0
    mock_session.return_value.run_cmd.return_value = mock_response

    compiled_command = session_faker.pystr()
    with patch.object(PowershellCommand, "compile", return_value=(compiled_command, [])):
        action = DisableUsersAction(data_path=symphony_storage)

        arguments1 = {
            "username": session_faker.word(),
            "password": session_faker.word(),
            "server": session_faker.word(),
            "users": [session_faker.word(), session_faker.word()]
        }

        result1 = action.run(arguments1)

        arguments2 = {
            "username": session_faker.word(),
            "password": session_faker.word(),
            "server": session_faker.word(),
            "sids": [session_faker.word(), session_faker.word()]
        }

        result2 = action.run(arguments2)

        assert result2 == {}


@pytest.mark.asyncio
async def test_disable_users_action_run_validation_error(symphony_storage: Path, session_faker: Faker):
    """
    Test run method of DisableUsersAction when invalid arguments are provided.

    Args:
        symphony_storage: Path
        session_faker: Faker
    """
    action = DisableUsersAction(data_path=symphony_storage)

    invalid_arguments = session_faker.pydict()

    with pytest.raises(ValidationError):
        action.run(invalid_arguments)
