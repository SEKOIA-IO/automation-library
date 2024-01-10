"""Tests for EnableUsersAction."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker

from actions import MicrosoftModule
from actions.enable_users_action import EnableUsersAction
from client.commands import PowershellCommand


@pytest.mark.asyncio
async def test_enable_users_action_success(
    symphony_storage: Path,
    mock_session: MagicMock,
    module: MicrosoftModule,
    session_faker: Faker,
):
    """
    Test run method of EnableUsersAction.

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
        action = EnableUsersAction(data_path=symphony_storage, module=module)

        arguments1 = {
            "users": [session_faker.word(), session_faker.word()],
            "server": session_faker.word(),
        }

        action.run(arguments1)

        arguments2 = {
            "sids": [session_faker.word(), session_faker.word()],
            "server": session_faker.word(),
        }

        result2 = action.run(arguments2)

        assert result2 == {}


@pytest.mark.asyncio
async def test_enable_users_action_validation_error(
    symphony_storage: Path, module: MicrosoftModule, session_faker: Faker
):
    """
    Test run method of EnableUsersAction when invalid arguments are provided.

    Args:
        symphony_storage: Path
        module: MicrosoftModule
        session_faker: Faker
    """
    action = EnableUsersAction(data_path=symphony_storage, module=module)

    invalid_arguments = session_faker.pydict()

    with pytest.raises(ValueError):
        action.run(invalid_arguments)
