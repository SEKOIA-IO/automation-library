"""Tests for ChangeUserPasswordAction."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker
from pydantic import ValidationError

from actions import MicrosoftModule
from actions.change_user_password_action import ChangeUserPasswordAction
from client.commands import PowershellCommand


@pytest.mark.asyncio
async def test_change_user_password_action_run_success(
    symphony_storage: Path,
    mock_session: MagicMock,
    module: MicrosoftModule,
    session_faker: Faker,
):
    """
    Test run method of ChangeUserPasswordAction.

    Args:
        symphony_storage: Path
        mock_session: MagicMock
        module: MicrosoftModule
        session_faker: Faker
    """
    mock_response = MagicMock()
    mock_response.status_code = 0
    mock_session.return_value.run_cmd.return_value = mock_response

    compiled_command = session_faker.pystr()
    with patch.object(PowershellCommand, "compile", return_value=(compiled_command, [])):
        action = ChangeUserPasswordAction(data_path=symphony_storage, module=module)

        # Test run method
        arguments = {
            "user_to_update": session_faker.word(),
            "new_password": session_faker.word(),
            "server": session_faker.word(),
        }

        result = action.run(arguments)

        assert result == {}


@pytest.mark.asyncio
async def test_change_user_password_action_run_validation_error(
    symphony_storage: Path, session_faker: Faker, module: MicrosoftModule
):
    """
    Test run method of ChangeUserPasswordAction when invalid arguments are provided.

    Args:
        symphony_storage: Path
        session_faker: Faker
        module: MicrosoftModule
    """
    action = ChangeUserPasswordAction(module=module, data_path=symphony_storage)

    invalid_arguments = session_faker.pydict()

    with pytest.raises(ValidationError):
        action.run(invalid_arguments)
