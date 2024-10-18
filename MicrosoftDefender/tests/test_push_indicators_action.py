from unittest.mock import patch

import pytest
from sekoia_automation.action import Action

from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.action_push_indicators import PushIndicatorsAction


def configured_action(action: Action):
    module = MicrosoftDefenderModule()
    a = action(module=module)

    a.module.configuration = {
        "servername": "test_servername",
        "admin_username": "test_admin_username",
        "admin_password": "test_admin_password",
    }

    return a


def test_push_indicators():
    pass
