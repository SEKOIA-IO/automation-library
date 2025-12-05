from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

from .samples import (
    sample_notifications,  # noqa: F401
    sample_sicalertapi,  # noqa: F401
    samplenotif_alert_created,  # noqa: F401
    samplenotif_alert_updated,  # noqa: F401
    samplenotif_alert_status_changed,  # noqa: F401
    samplenotif_alert_comment_created,  # noqa: F401
    samplenotif_case_created,  # noqa: F401
    samplenotif_case_updated,  # noqa: F401
    samplenotif_case_has_new_alert,  # noqa: F401
    samplenotif_case_has_updated_alerts,  # noqa: F401
    sample_case_notifications,  # noqa: F401
    sample_siccaseapi,  # noqa: F401
)


@pytest.fixture
def module_configuration():
    yield {"base_url": "http://fake.url/", "api_key": "fake_api_key"}


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage
