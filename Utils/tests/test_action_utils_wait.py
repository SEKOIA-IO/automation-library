from unittest.mock import patch

from utils.action_utils_wait import UtilsWait


def test_action_wait_incorrect_param():
    action = UtilsWait()

    with patch("utils.action_utils_wait.sleep") as mock_time:
        action.run(arguments={"duration": -100})
        mock_time.assert_called_once_with(0)

    with patch("utils.action_utils_wait.sleep") as mock_time:
        action.run(arguments={"duration": 10000})
        mock_time.assert_called_once_with(3600)


def test_action_wait_normal():
    with patch("utils.action_utils_wait.sleep") as mock_time:
        action = UtilsWait()

        action.run(arguments={"duration": 72})
        mock_time.assert_called_once_with(72)
