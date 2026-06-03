from unittest.mock import MagicMock

import pytest
from sekoia_automation.exceptions import ModuleConfigurationError

from netskope_modules.actions.action_append_to_blocklist import AppendToBlocklistAction
from netskope_modules.actions.action_base import NetskopeActionArguments


@pytest.fixture
def base_action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = AppendToBlocklistAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_api_token_missing_should_raise_explicit_message(base_action):
    with pytest.raises(
        ModuleConfigurationError,
        match="The API token is undefined. Please set it in action arguments",
    ):
        _ = base_action.api_token


def test_api_token_empty_should_raise_explicit_message(base_action):
    base_action.initialize_action_arguments(NetskopeActionArguments(api_token=""))

    with pytest.raises(
        ModuleConfigurationError,
        match="The API token is undefined. Please set it in action arguments",
    ):
        _ = base_action.api_token
