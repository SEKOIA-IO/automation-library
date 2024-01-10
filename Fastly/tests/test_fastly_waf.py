from unittest.mock import MagicMock

import pytest
from sekoia_automation.module import Module

from fastly_waf.connector_fastly_waf import FastlyWAFConnector


@pytest.fixture
def trigger(data_storage):
    module = Module()
    trigger = FastlyWAFConnector(module=module, data_path=data_storage)

    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "email": "john.doe@example.com", "token": "aaabbb", "corp": "some_corp", "site": "some.site.com"
    }
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60}
    yield trigger
