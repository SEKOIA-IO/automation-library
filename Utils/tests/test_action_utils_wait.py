from unittest.mock import patch

import pytest

from utils.action_utils_wait import UtilsWait


def test_action_wait_no_param():
    action = UtilsWait()

    with pytest.raises(ValueError):
        action.run(arguments={})


def test_action_wait_invalid_param():
    action = UtilsWait()

    with pytest.raises(ValueError):
        action.run(arguments={"duration": -100})

    with pytest.raises(ValueError):
        action.run(arguments={"duration": 10000})


def test_action_wait_normal():
    with patch("utils.action_utils_wait.sleep") as mock_time:
        action = UtilsWait()

        action.run(arguments={"duration": 72})

        mock_time.assert_called_once_with(72)
