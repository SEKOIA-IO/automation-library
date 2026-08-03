import os
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import MagicMock

import pytest
from sekoia_automation import constants

from netskope_modules import NetskopeModule
from netskope_modules.connectors.connector_pull_events_v2 import NetskopeEventConnector


@pytest.fixture
def credentials():
    yield {
        "type": "service_account",
        "project_id": "myproject",
        "private_key_id": "private_key_id",
        "private_key": "private_key",
        "client_email": "client_email",
        "client_id": "client_id",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/iam.gserviceaccount.com",
    }


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def trigger(symphony_storage):
    module = NetskopeModule()
    module._trigger_configuration_uuid = "ec92e51c-d45e-47b1-b820-29b97721623f"
    connector = NetskopeEventConnector(module=module, data_path=symphony_storage)
    # Avoid network access in unit tests.
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    connector.module.configuration = {
        "base_url": "https://my.fake.sekoia",
        "api_token": "fake_api_token",
    }
    connector.configuration = {
        "api_token": "api_token",
        "intake_key": "intake_key",
        "consumer_group": "",
    }
    return connector


@pytest.fixture
def integration_trigger(symphony_storage):
    module = NetskopeModule()
    module._community_uuid = "ec92e51c-d45e-47b1-b820-29b97721623f"
    connector = NetskopeEventConnector(module=module, data_path=symphony_storage)
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    connector.module.configuration = {
        "base_url": os.environ["NETSKOPE_BASE_URL"],
        "api_token": os.environ["NETSKOPE_API_TOKEN"],
    }
    connector.configuration = {
        "api_token": os.environ["NETSKOPE_API_TOKEN"],
        "intake_key": "0123456789",
    }
    return connector
