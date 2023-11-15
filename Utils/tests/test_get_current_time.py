from utils.action_get_current_time import (
    GetCurrentTimeAction,
    Arguments,
)
from re import match
from shutil import rmtree
from tempfile import mkdtemp


import pytest

from sekoia_automation import constants


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.SYMPHONY_STORAGE = original_storage


def testGetCurrentTime():
    action = GetCurrentTimeAction()
    request = Arguments(selectedTimezone="UTC 0")
    reponse = action.run(request)
    assert match(r"^[0-9]+$", str(reponse["epoch"]))
    assert match(
        r"^[0-9]{4}\-[0-9]{2}\-[0-9]{2}T[0-2][0-9]:[0-5][0-9]:[0-5][0-9].[0-9]{6}$",
        reponse["iso8601"],
    )
