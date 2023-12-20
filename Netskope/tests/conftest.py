from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants


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
